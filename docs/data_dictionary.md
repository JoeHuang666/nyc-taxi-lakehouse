# Data dictionary

| Artifact | Grain | Meaning |
|---|---|---|
| Bronze | source row, multiplicity preserved | Original source fields plus month, checksum, load timestamp |
| Silver | eligible source row | NYC pickup with valid local time and matching source month |
| Quarantine | excluded source row | Primary reason and array of all reasons |
| dim_zone | zone_id | Official zone name, borough, service and NYC membership |
| dim_hour | hour_key | UTC epoch hours, NYC local date/hour/weekday/offset |
| fact_zone_hourly | zone_id, hour_key | Eligible pickup count, source coverage |
| fact_zone_daily | zone_id, local_date | Pickups, fee-eligible count and recorded total charges |
| features | zone_id, hour_key | Whitelisted past-only values; no target label |
| labels | zone_id, hour_key | Actual pickup count |
| forecast_comparison | zone_id, hour_key | One actual and baseline/candidate predictions per key |
| quality_summary | source_month | Conservation, exclusion reasons and anomaly counts |

Fees are decimal(18,2); recorded charges are not driver profit and exclude cash tips.
zone_id is categorical, never a geographic distance.
UTC hour keys are numeric; Power BI must not convert local strings into the viewer's timezone.
source_covered is an ingestion assumption, not a guarantee of source-vendor completeness.
A source-row fingerprint is not a unique trip identifier; no such identifier is invented.
