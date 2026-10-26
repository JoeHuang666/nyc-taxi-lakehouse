from __future__ import annotations
import hashlib
import pickle
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder
from threadpoolctl import threadpool_limits
from .common import json_write, now
from .features import FEATURES, NUMERIC

def metrics(actual, predicted):
    actual, predicted = np.asarray(actual, float), np.asarray(predicted, float)
    if not len(actual) or actual.shape != predicted.shape:
        raise ValueError("Empty or unequal evaluation keys")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all() or (predicted < 0).any():
        raise ValueError("Invalid actuals/predictions")
    error = np.abs(actual-predicted)
    return {"n": len(actual), "mae": float(error.mean()),
            "wape": float(error.sum()/actual.sum()) if actual.sum() else None,
            "actual_total": float(actual.sum()), "absolute_error_total": float(error.sum())}

def estimator(params, seed):
    preprocessing = ColumnTransformer([("zone", OneHotEncoder(handle_unknown="error", sparse_output=False), ["zone_id"]),
                                       ("numeric", "passthrough", NUMERIC)])
    return make_pipeline(preprocessing, HistGradientBoostingRegressor(
        loss="poisson", early_stopping=False, learning_rate=.05, max_iter=200,
        random_state=seed, **params))

def train_and_replay(run_dir, built, cfg, fingerprint):
    x = pd.read_parquet(run_dir / "features.parquet")
    labels = pd.read_parquet(run_dir / "labels.parquet")
    data = x.merge(labels, on=["zone_id", "hour_key"], validate="one_to_one")
    train = data[(data.local_date >= "2024-01-08") & (data.local_date < "2024-02-16")]
    validation = data[(data.local_date >= "2024-02-16") & (data.local_date < "2024-03-01")]
    refit = data[(data.local_date >= "2024-01-08") & (data.local_date < "2024-03-01")]
    test_x = x[(x.local_date >= "2024-03-01") & (x.local_date < "2024-04-01")]
    if len(test_x) != 743 * cfg["top_zones"] or train.hour_key.max() >= validation.hour_key.min():
        raise ValueError("Split coverage/boundary failed")
    options = [{"max_leaf_nodes": 15, "l2_regularization": 1.0},
               {"max_leaf_nodes": 31, "l2_regularization": 1.0},
               {"max_leaf_nodes": 31, "l2_regularization": 10.0}]
    results = []
    baseline_validation = metrics(validation.actual, validation.baseline_pred)
    with threadpool_limits(limits=4):
        for params in options:
            candidate = estimator(params, cfg["seed"])
            candidate.fit(train[FEATURES], train.actual)
            score = metrics(validation.actual, candidate.predict(validation[FEATURES]))
            results.append({"params": params, "metrics": score})
            print(f"VALIDATION {params}: MAE={score['mae']:.4f}", flush=True)
        best = min(results, key=lambda r: r["metrics"]["mae"])
        selected = "candidate" if best["metrics"]["mae"] < baseline_validation["mae"]-1e-6 else "baseline"
        model_id = hashlib.sha256((fingerprint + str(best["params"])).encode()).hexdigest()[:16]
        frozen = {"model_id": model_id, "selected_method": selected, "selected_params": best["params"],
                  "feature_columns": FEATURES, "validation": results, "baseline_validation": baseline_validation,
                  "frozen_at_utc": now(), "test_used_for_selection": False,
                  "train_range": ["2024-01-08", "2024-02-16"], "validation_range": ["2024-02-16", "2024-03-01"],
                  "refit_range": ["2024-01-08", "2024-03-01"], "test_range": ["2024-03-01", "2024-04-01"],
                  "selected_zones": built["selected_zones"], "dependency_hash": fingerprint}
        # Persist selection before any test scoring.
        json_write(run_dir / "model_selection.json", frozen)
        final = estimator(best["params"], cfg["seed"])
        final.fit(refit[FEATURES], refit.actual)
        with (run_dir / "model.pkl").open("wb") as f:
            pickle.dump(final, f)
        frames = []
        for hour, batch in test_x.sort_values("hour_key").groupby("hour_key", sort=True):
            if not (batch.max_history_hour_end <= hour).all():
                raise ValueError("Future history in replay")
            predictions = final.predict(batch[FEATURES])
            frames.append(batch[["zone_id", "hour_key", "local_date", "local_hour", "weekday", "weekend",
                                 "baseline_pred", "dst_fallback"]].assign(candidate_pred=predictions))
        forecast = pd.concat(frames, ignore_index=True)
    forecast = forecast.merge(labels, on=["zone_id", "hour_key"], validate="one_to_one")
    if len(forecast) != len(test_x) or forecast.duplicated(["zone_id", "hour_key"]).any():
        raise ValueError("Replay keys mismatch")
    thresholds = refit.groupby("zone_id").actual.quantile(.9)
    forecast["peak"] = forecast.actual >= forecast.zone_id.map(thresholds)
    forecast["selected_method"] = selected
    forecast["model_id"] = model_id
    forecast["split"] = "test"
    forecast["baseline_abs_error"] = abs(forecast.actual-forecast.baseline_pred)
    forecast["candidate_abs_error"] = abs(forecast.actual-forecast.candidate_pred)
    forecast["selected_pred"] = forecast[f"{selected}_pred"]
    forecast["week"] = pd.to_datetime(forecast.local_date).dt.isocalendar().week.astype(int)
    baseline = metrics(forecast.actual, forecast.baseline_pred)
    candidate = metrics(forecast.actual, forecast.candidate_pred)
    result = {**frozen, "test": {"baseline": baseline, "candidate": candidate,
              "relative_mae_improvement": 1-candidate["mae"]/baseline["mae"] if baseline["mae"] else None,
              "coverage": len(forecast)/(743*cfg["top_zones"]), "expected_rows": 743*cfg["top_zones"]},
              "peak_thresholds": thresholds.to_dict(), "replay_hours": len(frames)}
    forecast.to_csv(run_dir / "forecast_comparison.csv", index=False)
    slices = []
    for dimension in ["zone_id", "week", "local_hour", "weekend", "peak"]:
        for key, group in forecast.groupby(dimension):
            for method in ["baseline", "candidate"]:
                slices.append({"dimension": dimension, "value": str(key), "method": method,
                               **metrics(group.actual, group[f"{method}_pred"])})
    pd.DataFrame(slices).to_csv(run_dir / "error_slices.csv", index=False)
    forecast.nlargest(3, "candidate_abs_error").to_csv(run_dir / "largest_errors.csv", index=False)
    json_write(run_dir / "metrics.json", result)
    print(f"TEST: baseline MAE={baseline['mae']:.4f}, candidate MAE={candidate['mae']:.4f}", flush=True)
    return result
