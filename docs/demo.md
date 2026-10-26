# Three-minute demo

I built a local data lakehouse for NYC Yellow Taxi records from the first quarter of 2024.
The goal is to make the data reproducible and evaluate next-hour pickup forecasts.

First, I preserve the raw files with checksums. Spark writes Bronze, Silver and Gold as
Delta tables. Invalid pickup times and unknown zones are quarantined, while negative
fares remain in pickup counts. Reprocessing a month replaces its partition rather than
duplicating it. Quality checks reconcile every stage.

Second, I use a continuous UTC calendar while keeping New York local business time.
This matters at daylight-saving transitions. The ten modeling zones are selected using
January only. The model learns from historical lags, rolling counts and calendar features.
Tests show that changing future values does not change earlier features.

Third, I compare a weekly seasonal baseline with one Poisson gradient-boosting model.
I select parameters on February, freeze the choice, and replay March hour by hour.
Please use the current release's metrics for the actual scores; I do not assume the model wins.

The dashboard separates historical operations from forecast evaluation. MAE is measured
in pickups per zone-hour; WAPE recomputes total absolute error divided by actual volume.
A lower error may support planning discussion, but this does not prove reduced waits
or increased revenue. TLC publishes monthly, so this is a historical simulation, not live dispatch.

Finally, the release contains source and code versions, quality evidence and reproducible
commands. This demonstrates local Spark engineering; cloud and multi-node operations
are outside the scope of this version.
