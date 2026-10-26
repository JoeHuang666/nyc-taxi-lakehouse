# Power BI dashboard

Report definitions are generated locally instead of committing another machine's absolute
CSV paths or binary caches. The English generator creates two pages: historical operations
and March one-hour replay. Python-rendered English previews are in `docs/images/`.

After a successful full pipeline run, from the repository root:

```sh
python tools/build_powerbi.py
python tools/polish_powerbi.py
```

Open `dashboard/Taxi.pbip` in Power BI Desktop, refresh the imported tables, and save a PBIX.
If your Desktop installation requires enabling Power BI project support, enable it and
restart Desktop first. Close the project before regenerating. Generation replaces report
and semantic model definitions; back up manual report edits first.

The generator uses `current_release.json` to bind one successful local release. If the
checkout moves, regenerate from a new valid local release instead of reusing stale paths.
Generated PBIP/PBIX files, the binding record, and `.pbi` caches are ignored by Git.
The original author's saved PBIX is retained outside this clean repository.

## Semantic model

`dim_zone` and `dim_hour` each filter `fact_zone_hourly` and `forecast_comparison` through
one-to-many, single-direction relationships. Fact tables are not directly joined.
MAE averages absolute error; WAPE divides summed absolute error by summed actual volume.
The generator also writes `measures.dax` for review.

## Verification

Reference Desktop checks matched Python to displayed precision:

| Selection | Actual pickups | Baseline MAE | Model MAE |
|---|---:|---:|---:|
| All March model zones | 1,309,004 | 31.35 | 25.21 |
| Zone 132, local hour 9 | 3,782 | 24.23 | 23.71 |
| Zone 239, local hour 18 | 7,094 | 42.81 | 27.58 |

Use your release's `bi_filter_checks.json` when validating a new run. The original Desktop
application chrome was localized; generated report labels and source definitions are English.
Daily/hourly chart axes may scroll. The weekday/hour view is a numeric matrix. Peak groups
use January–February per-zone 90th-percentile thresholds.
