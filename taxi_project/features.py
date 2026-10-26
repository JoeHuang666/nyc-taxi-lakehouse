from __future__ import annotations
import numpy as np
import pandas as pd
from .common import ROOT
from .lakehouse import calendar
from .spark_session import read_delta, write_delta

NUMERIC = ["local_hour", "weekday", "weekend", "utc_offset", "lag_1", "lag_2",
           "lag_24", "lag_168", "rolling_3", "rolling_24", "rolling_168", "baseline_pred", "dst_fallback"]
FEATURES = ["zone_id"] + NUMERIC

def add_calendar_and_baseline(lags, history):
    """Labels stay outside X; weekly lookup only reads the preceding local week."""
    cal = calendar()
    x = lags.merge(cal.drop(columns="source_month"), on="hour_key", validate="many_to_one")
    target_local = pd.to_datetime(x.local_date) + pd.to_timedelta(x.local_hour, unit="h")
    previous = (target_local - pd.Timedelta(days=7)).dt.tz_localize("America/New_York", nonexistent="NaT", ambiguous="raise")
    fallback = previous.isna()
    previous_key = previous.dt.tz_convert("UTC").astype("int64") // 10**9 // 3600
    previous_key = previous_key.where(~fallback, x.hour_key - 168)
    lookup = history.set_index(["zone_id", "hour_key"]).trip_count
    keys = pd.MultiIndex.from_arrays([x.zone_id, previous_key])
    x["baseline_pred"] = lookup.reindex(keys).to_numpy()
    x["dst_fallback"] = fallback.astype(int)
    x["max_history_hour_end"] = x.hour_key
    return x

def reference_features(history, targets=None):
    """Independent pandas oracle used for prefix/future tests and replay checks."""
    h = history.sort_values(["zone_id", "hour_key"]).copy()
    for _, part in h.groupby("zone_id"):
        if not np.all(np.diff(part.hour_key) == 1):
            raise ValueError("History must use a dense hourly calendar")
    out = h[["zone_id", "hour_key"]].copy()
    grouped = h.groupby("zone_id").trip_count
    for k in [1, 2, 24, 168]:
        out[f"lag_{k}"] = grouped.shift(k)
    for k in [3, 24, 168]:
        out[f"rolling_{k}"] = grouped.transform(lambda s: s.shift().rolling(k, min_periods=k).mean())
    x = add_calendar_and_baseline(out, h)
    return x if targets is None else x[x.hour_key.isin(targets)]

def build_features(spark, built, run_dir):
    lake = built["lake"]
    history = read_delta(spark, f"{lake}/gold_hourly", built["versions"]["gold_hourly"])
    zones = [r["zone_id"] for r in built["selected_zones"]]
    history = history.filter(history.zone_id.isin(zones))
    if history.count() > 100000:
        raise ValueError("Refusing large collection")
    history.createOrReplaceTempView("selected_hourly")
    lags = spark.sql((ROOT / "sql/features.sql").read_text()).toPandas()
    h = history.select("zone_id", "hour_key", "trip_count").toPandas()
    if h.duplicated(["zone_id", "hour_key"]).any() or len(h) != 2183 * len(zones):
        raise ValueError("Invalid hourly panel")
    x = add_calendar_and_baseline(lags, h).sort_values(["zone_id", "hour_key"]).reset_index(drop=True)
    # Partial SQL frames during warmup cannot count as complete history.
    x.loc[x.lag_168.isna(), ["rolling_3", "rolling_24", "rolling_168"]] = np.nan
    oracle = reference_features(h).sort_values(["zone_id", "hour_key"]).reset_index(drop=True)
    valid = x.lag_168.notna()
    np.testing.assert_allclose(x.loc[valid, FEATURES], oracle.loc[valid, FEATURES], equal_nan=True, rtol=1e-10)
    for cutoff in [int(x.hour_key.min()+200), int(x.hour_key.max()-24)]:
        prefix = h[h.hour_key <= cutoff].copy()
        # The target's value is deliberately unknowable at prediction time.
        prefix.loc[prefix.hour_key == cutoff, "trip_count"] = np.nan
        at_t = reference_features(prefix, [cutoff]).sort_values("zone_id")
        full = x[x.hour_key == cutoff].sort_values("zone_id")
        np.testing.assert_allclose(at_t[FEATURES], full[FEATURES], equal_nan=True)
    x = x.dropna(subset=FEATURES).copy()
    labels = h.rename(columns={"trip_count": "actual"})[["zone_id", "hour_key", "actual"]]
    x.to_parquet(run_dir / "features.parquet", index=False)
    labels.to_parquet(run_dir / "labels.parquet", index=False)
    version = write_delta(spark.createDataFrame(x.to_dict("records")), f"{lake}/features")
    label_version = write_delta(spark.createDataFrame(labels.to_dict("records")), f"{lake}/labels")
    return {"features_version": version, "labels_version": label_version, "rows": len(x),
            "feature_columns": FEATURES, "prefix_checks": 2, "sql_oracle_match": True}
