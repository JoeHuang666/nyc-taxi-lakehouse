# Model card
Task: next-hour eligible pickup count for January's ten busiest NYC Yellow Taxi zones.
Model: pooled HistGradientBoostingRegressor, Poisson loss, dense one-hot zones.
Seed: 42. Early stopping disabled. Parameters: {'max_leaf_nodes': 31, 'l2_regularization': 10.0}.
Train: Jan 8–Feb 15. Validate: Feb 16–29. Refit: Jan 8–Feb 29. Test: March.
Features: zone_id, local_hour, weekday, weekend, utc_offset, lag_1, lag_2, lag_24, lag_168, rolling_3, rolling_24, rolling_168, baseline_pred, dst_fallback.
Selection was saved before test scoring. No test-guided parameter search.
Baseline: previous local week; only nonexistent DST hours use 168 elapsed hours.
Performance and limitations: see report.md and metrics.json.
Trusted local model binary: runs/20261025T160102-15f12a/model.pkl. Never load untrusted pickle files.
