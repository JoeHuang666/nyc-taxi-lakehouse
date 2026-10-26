# Learning and review guide

1. Read the reference report to understand input volume, exclusions and model performance.
2. Follow `sql/zone_hourly.sql`: how do individual trips become zone-hour counts?
3. Inspect `taxi_project/lakehouse.py`: why do negative fares remain valid pickups?
4. Read `sql/features.sql`: why does each rolling window end at `1 PRECEDING`?
5. Calculate `lag_1`, `lag_24`, and `rolling_3` for a chosen 09:00 row by hand.
6. Explain why an hourly replay may use earlier March actuals but not the target hour's label.
7. Compare `model_selection.json` and `metrics.json`: validation chooses; testing evaluates.
8. Run the sample profile and inspect its manifest and quality results. Do not present sample scores as full results.
9. In Power BI, filter a model zone and local hour and compare DAX to `bi_filter_checks.json`.
10. Practice the [demo](demo.md), using the metrics from the release you actually show.

Independent reproduction and explaining these decisions are learning goals. Automated
execution by another person or an agent does not demonstrate your own understanding.
