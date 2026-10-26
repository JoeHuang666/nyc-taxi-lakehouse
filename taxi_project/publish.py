from __future__ import annotations
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .common import ROOT, digest, json_write, promote
from .model import metrics
from .spark_session import read_delta

def export_spark_csv(df, destination):
    # Stream rows; never collect the whole all-zone hourly table into the driver.
    import csv
    with Path(destination).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(df.columns)
        for row in df.toLocalIterator():
            writer.writerow(list(row))

def publish(spark, built, trained, run_dir, manifest):
    release = ROOT / "releases" / run_dir.name
    release.mkdir(parents=True, exist_ok=False)
    versions, lake = built["versions"], Path(built["lake"])
    for table, name in [("dim_zone", "dim_zone"), ("dim_hour", "dim_hour"),
                        ("gold_hourly", "fact_zone_hourly"), ("gold_daily", "fact_zone_daily")]:
        export_spark_csv(read_delta(spark, lake / table, versions[table]), release / f"{name}.csv")
    for name in ["forecast_comparison.csv", "error_slices.csv", "largest_errors.csv", "metrics.json", "model_selection.json"]:
        shutil.copyfile(run_dir / name, release / name)
    pd.json_normalize(built["quality"]).to_csv(release / "quality_summary.csv", index=False)
    forecast = pd.read_csv(release / "forecast_comparison.csv")
    for method in ["baseline", "candidate"]:
        recomputed = metrics(forecast.actual, forecast[f"{method}_pred"])
        np.testing.assert_allclose(recomputed["mae"], trained["test"][method]["mae"], rtol=1e-12)
    actual_sum = 0
    for part in pd.read_csv(release / "fact_zone_hourly.csv", chunksize=100000):
        actual_sum += int(part.trip_count.sum())
    if actual_sum != sum(q["silver_count"] for q in built["quality"]):
        raise ValueError("Export conservation failed")
    checks = []
    for zone, hour in [(int(forecast.zone_id.min()), 9), (int(forecast.zone_id.max()), 18)]:
        part = forecast[(forecast.zone_id == zone) & (forecast.local_hour == hour)]
        checks.append({"zone_id": zone, "local_hour": hour,
                       "baseline": metrics(part.actual, part.baseline_pred),
                       "candidate": metrics(part.actual, part.candidate_pred)})
    json_write(release / "bi_filter_checks.json", checks)
    make_report(release, built, trained, manifest)
    files = {p.name: digest(p) for p in release.iterdir() if p.is_file()}
    json_write(release / "release_manifest.json", {"status": "SUCCESS", "run_id": run_dir.name,
        "dependency_hash": manifest["dependency_hash"], "versions": versions,
        "model_id": trained["model_id"], "files": files})
    promote(release)
    return release

def make_report(release, built, trained, manifest):
    daily = pd.read_csv(release / "fact_zone_daily.csv")
    forecast = pd.read_csv(release / "forecast_comparison.csv")
    zones = pd.read_csv(release / "dim_zone.csv").set_index("zone_id").zone_name
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), layout="constrained")
    totals = daily.groupby("local_date").trip_count.sum()
    axes[0].plot(pd.to_datetime(totals.index), totals.values, color="#007c91")
    axes[0].set(title="Recorded eligible Yellow Taxi pickups | NYC 2024 Q1", ylabel="Pickups per day")
    ranking = daily.groupby("zone_id").trip_count.sum().nlargest(10).sort_values()
    axes[1].barh([zones.loc[z] for z in ranking.index], ranking.values, color="#007c91")
    axes[1].set(title="Highest-volume zones across Q1 (descriptive only)", xlabel="Recorded pickups")
    fig.savefig(release / "operations.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), layout="constrained")
    zone = built["selected_zones"][0]["zone_id"]
    example = forecast[(forecast.zone_id == zone) & (forecast.local_date >= "2024-03-11") & (forecast.local_date < "2024-03-14")]
    for column, label in [("actual", "Actual"), ("baseline_pred", "Weekly baseline"), ("candidate_pred", "Candidate")]:
        axes[0].plot(pd.to_datetime(example.hour_key*3600, unit="s", utc=True), example[column], label=label)
    axes[0].legend()
    axes[0].set(title=f"Historical one-hour replay | {zones.loc[zone]}", ylabel="Pickups", xlabel="UTC")
    scores = forecast.groupby("zone_id")[["baseline_abs_error", "candidate_abs_error"]].mean()
    scores.index = scores.index.map(zones)
    scores.rename(columns={"baseline_abs_error": "Baseline", "candidate_abs_error": "Candidate"}).plot.bar(ax=axes[1], rot=25)
    axes[1].set(ylabel="MAE (pickups / zone-hour)", xlabel="")
    fig.savefig(release / "forecast.png", dpi=150)
    plt.close(fig)
    b, c = trained["test"]["baseline"], trained["test"]["candidate"]
    raw = sum(q["raw_count"] for q in built["quality"])
    valid = sum(q["silver_count"] for q in built["quality"])
    text = f"""# Run report: {release.name}

This is an offline historical one-hour replay, not a live prediction service.

- Raw rows: {raw:,}; eligible pickups: {valid:,}; quarantined: {raw-valid:,}.
- Full Q1 calendar: 2,183 actual hours. March predictions: {c['n']:,}, coverage {trained['test']['coverage']:.1%}.
- Weekly baseline MAE: {b['mae']:.4f}; candidate MAE: {c['mae']:.4f}.
- Weekly baseline WAPE: {b['wape']:.2%}; candidate WAPE: {c['wape']:.2%}.
- Relative candidate MAE improvement: {trained['test']['relative_mae_improvement']:.2%}.
- Method selected using February validation only: {trained['selected_method']}.
- Model ID: {trained['model_id']}.

![Operations](operations.png)
![Forecast evaluation](forecast.png)

## Interpretation
The model estimates eligible recorded pickups for ten zones selected using January.
A lower MAE may support staffing discussion; it does not establish additional revenue,
reduced waiting time, unmet demand, or the number of vehicles to dispatch.
The three largest model errors are in largest_errors.csv. Unobserved events, weather,
and traffic are possible omitted factors; no causal attribution was verified.

## Limitations
The prior hour is assumed fully available at each boundary. TLC monthly publication
does not meet this assumption. Original publication/revision histories are unavailable.
Zero-filled cells assume a successfully ingested complete monthly source.
This is local Spark on one machine; no distributed-load or cloud benchmark was performed.
Power BI visual acceptance is separate from the verified export metrics.
"""
    (release / "report.md").write_text(text, encoding="utf-8")
    (release / "model_card.md").write_text(f"""# Model card
Task: next-hour eligible pickup count for January's ten busiest NYC Yellow Taxi zones.
Model: pooled HistGradientBoostingRegressor, Poisson loss, dense one-hot zones.
Seed: 42. Early stopping disabled. Parameters: {trained['selected_params']}.
Train: Jan 8–Feb 15. Validate: Feb 16–29. Refit: Jan 8–Feb 29. Test: March.
Features: {', '.join(trained['feature_columns'])}.
Selection was saved before test scoring. No test-guided parameter search.
Baseline: previous local week; only nonexistent DST hours use 168 elapsed hours.
Performance and limitations: see report.md and metrics.json.
Trusted local model binary: runs/{release.name}/model.pkl. Never load untrusted pickle files.
""", encoding="utf-8")
