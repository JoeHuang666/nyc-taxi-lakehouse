# Reference experiment evidence

Recorded on 2026-10-25, before repository packaging.
Run: `20261025T160102-15f12a`; model: `aa0faee5b6a04b0f`.
These files are a small historical evidence bundle, not a complete executable release.
The original run directory, local model pickle, raw data and full exports are not included.

| File | Meaning |
|---|---|
| [report.md](report.md) | Original numerical summary |
| [metrics.json](metrics.json) | Validation candidates, held-out scores and coverage |
| [model_selection.json](model_selection.json) | Choice persisted before held-out scoring |
| [model_card.md](model_card.md) | Model features, split and assumptions |
| [quality_summary.csv](quality_summary.csv) | Monthly conservation and exclusion counts |
| [bi_filter_checks.json](bi_filter_checks.json) | Python values for Desktop DAX comparison |
| [error_slices.csv](error_slices.csv) | Error broken down by evaluation slice |
| [largest_errors.csv](largest_errors.csv) | Largest model errors |
| [full-rerun.json](full-rerun.json) | Exact full-volume ETL rerun reconciliation |
| [release_manifest.json](release_manifest.json) | Original full release file hashes and Delta versions |

The release manifest includes hashes for large exports omitted from this bundle. Its
original code/environment fingerprint is historical; repository tooling and documentation
have subsequently changed. Reproduction creates a new run ID, manifest and local release.
The plots in `docs/images/` are copied from the same reference release.
