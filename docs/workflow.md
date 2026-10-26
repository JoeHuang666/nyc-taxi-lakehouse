# Workflow and output contracts

Run all commands from the repository root. Use the same source directory on resume.

| Step | Command | Output |
|---|---|---|
| Smoke check | `python -m taxi_project doctor` | `reports/doctor.json`, isolated Delta table |
| Download | `python tools/download_data.py --output downloads` | Four hash-verified files |
| Ingest only | `python -m taxi_project ingest --source-dir downloads` | Content-addressed raw files and source manifest |
| Small pipeline | `python -m taxi_project run --profile sample --source-dir downloads` | Separate sample Delta tables, manifest, quality checks |
| Full experiment | `python -m taxi_project run --profile full --source-dir downloads` | Full Delta tables, features, model, scored release |
| Full ETL comparison | `python tools/verify_full.py` | Exact multiset comparison; current release unchanged |
| Generate BI | `python tools/build_powerbi.py` then `python tools/polish_powerbi.py` | Editable local PBIP |

`run` performs ingestion, build, features, training/replay, export and promotion in order.
`build` stops after the lakehouse stage. The legacy `train`, `backtest`, and `publish` CLI
names require `--run-id` and execute the remaining pipeline, not isolated single stages;
prefer the documented `run` and `resume` commands.

## Runtime layout

```text
downloads/                    # Downloaded input files
data/raw/<sha256>/             # Immutable imported snapshots
data/source_manifest.json     # Source hashes, schema, rows and local paths
data/lakehouse/sample/        # Isolated sample Delta tables
data/lakehouse/full/          # Bronze, Silver, quarantine, Gold and dimensions
runs/<run_id>/                # Manifest, build checkpoint, features, selection, model
releases/<run_id>/            # CSV exports, metrics, plots and model card
current_release.json          # Pointer to the last completely checked release
reports/                      # Smoke and rerun evidence
```

The reference artifacts committed under `reports/reference/` are historical evidence,
not a runnable release or a replacement for your own `current_release.json`.

## Recovery

```sh
python -m taxi_project resume --run-id YOUR_RUN_ID --profile full --source-dir downloads
```

Resume checks source, configuration, code and environment fingerprints, then reads pinned
Delta versions from a successful whole-build checkpoint. If dependencies changed, start a
fresh run. If the checkpoint is missing, processing starts again. There is no partial-month
checkpoint reuse. `--force-build` rebuilds even when a reusable checkpoint exists.

A writer lock excludes concurrent writers. Failed runs keep their traceback and do not
promote an incomplete release. Do not delete Delta history that a checkpoint still references.
Only load pickle models you trust. End-to-end injected failure recovery remains untested.

## Publication

Exports are reconciled against source aggregates; metrics are recalculated from predictions.
A release manifest records checksums. Only then does an atomic pointer update expose the
release. Power BI imports one fixed release, so users do not see mixed table versions.
