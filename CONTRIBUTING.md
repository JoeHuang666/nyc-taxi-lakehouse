# Contributing

Use Python 3.11 and follow [setup](docs/setup.md). Keep changes small and include the test
that protects the behavior you change. Keep code comments, documentation, report labels,
and error messages in English.

```sh
python -m pytest -q
python -m pytest -q --run-spark
```

For changes to data cleaning, calendars or aggregation, rerun both profiles and compare full
results. For feature/model changes, preserve time-based selection and rerun the held-out
experiment. Never tune against March and continue calling it an untouched test set.

Do not commit raw trips, generated models, cached Power BI data, logs, credentials or local
absolute paths. Check `git status --short` and `git diff --cached` before publishing.
The `reports/reference/` directory documents an immutable historical experiment: add new
evidence separately instead of replacing old scores without explanation.

CI runs a synthetic Spark fixture, not the 9.55-million-row workload or Power BI Desktop.
A successful CI run is not evidence of complete data/BI reproduction.
