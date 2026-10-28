# Acceptance evidence — 2026-10-25

Full run: 20261025T160102-15f12a. Model: aa0faee5b6a04b0f.
The pipeline completed in 155.98 seconds on the user's local Windows computer,
excluding downloads and BI rendering. This is not a distributed benchmark.

| Check | Evidence / status |
|---|---|
| E01 environment | Existing smoke acceptance; full Spark/Delta run succeeded |
| D01 sources | Four SHA-256-addressed raw snapshots and source_manifest.json |
| D02 schemas | All three Arrow schemas checked; explicit timezone/zone/decimal conversions |
| D03 conservation | 9,554,778 raw = 9,517,009 Silver + 37,769 quarantine; Gold/export totals agree |
| D04 lookup join | Unique zone IDs checked before join; row conservation enforced |
| D05 negative fares | Spark fixture confirms valid pickup with negative charge is retained |
| D06 missing vs zero | Required source files and city-hour coverage gate; dense-history gap test |
| D07 DST | 2,183 Q1 hours; March 10 = 23 hours; nonexistent pickup fixture quarantined |
| R01 rerun | Full ETL rerun: 571,946 hourly and 20,355 daily rows exactly equal via exceptAll both ways; quality identical; published release unchanged. reports/reference/full-rerun.json; 149.17 seconds |
| R02 failed release | Unit test confirms incomplete/failed release cannot replace current pointer |
| R03 dependencies | Tests confirm source/config changes alter checkpoint fingerprint |
| F01/F02/F03 | Hand-calculated lags/rolling, future mutation, prefix invariance; full SQL matches pandas oracle |
| M01 split/freeze | model_selection.json persisted before test scoring; no internal random early-stopping split |
| M02 fair keys | Shared one-row-per-zone-hour forecast, 7,430 identical evaluation keys |
| M03 complete replay | 743 hourly model calls, ten fixed zones, 100% March coverage |
| B01 metric math | MAE/WAPE and zero denominator tests; export metrics rechecked |
| B02 BI measures | Desktop full results and DAX two filter cases match Python to displayed precision |
| P01 reproduction | User launched sample, full pipeline and tests via documented host Python commands; fresh-machine recreation pending |
| P02 deliverables | Real PBIP and PBIX; two pages loaded in Desktop; model card and English demo saved |

Original host tests: 9 passed in 76.19 seconds. The local host log is not distributed.
The initial Spark fixture failed because naive Python datetimes were interpreted in the
host timezone. Only the fixture was corrected to cast explicit source wall-clock strings
inside Spark; production Parquet processing and model rules were unchanged.

## Remaining limits
- Full ETL was repeated and reconciled; model training was not repeated in this rerun.
- An injected mid-build failure/resume scenario has not been executed end-to-end.
  Whole-build checkpoint resume exists; partial-month recovery reuse does not.
- Clean-machine dependency recreation and independent learning remain unverified.
- Spark shutdown temporary JAR deletion warnings remain. Native-path configuration fixed
  the suspicious-URI warning, but the JAR cleanup root cause is not conclusively established.
- No cloud, multi-node, live-feed or causal business impact was tested.

## Repository packaging

The clean English repository retains historical reference evidence, excludes machine-local
state, and generates Power BI files from each user's own full release. Original PBIX
files and host logs remain in the author's working directory, outside this repository.
GitHub Actions completed successfully on 2026-10-28: 12 tests passed in 43.60 seconds
on a fresh Ubuntu runner with Python 3.11 and Java 17, including the Spark/Delta fixture.
Evidence: https://github.com/JoeHuang666/nyc-taxi-lakehouse/actions/runs/40685318583
This verifies dependency installation and synthetic integration tests, not a new full-data run.

Repository checks on 2026-10-26: 11 unit tests passed; the Spark integration fixture
was skipped in this packaging pass. All four source hashes match the original inputs.
Power BI generation and styling ran from outside the repository root and produced five
tables, four relationships and two pages. This is a structural generation check, not a
new Desktop visual acceptance or full data run.
