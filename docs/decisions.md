# Implementation decisions
2026-10-25:
- Use a flat taxi_project package so python -m taxi_project works directly from the checkout
  without an editable install. Combine related stages into lakehouse.py and model.py.
- Start at local[4], 6 GB driver heap, 16 shuffle partitions to leave room for Power BI.
- Preserve Arrow timestamp[us] local wall-clock fields, explicitly convert NYC to UTC.
- Capture imported_at time separately; original user download retrieval time is unknown.
- Host PowerShell execution was necessary: the agent sandbox blocked localhost first, then
  Hadoop _delta_log directory listing even after narrowly scoped grants.
- Native Windows spark.local.dir removes the suspicious-URI warning. Shutdown JAR cleanup
  warnings remain; no arbitrary Java process termination or broad deletion is performed.
- A successful whole-build checkpoint can be reused. Per-month recovery checkpoint reuse
  is not yet implemented; a partial build restarts its monthly processing.
- Q1 hourly exports are streamed from Spark; model collections have an explicit 100k-row cap.
- Power BI uses text-based project definitions where possible, followed by Desktop validation.
- The architecture document records the design; acceptance.md distinguishes implementation from evidence.

2026-10-26 repository packaging:
- Keep the validated working directory intact and export a separate clean repository.
- Keep all repository text in English; generate machine-bound Power BI files locally.
- Add a pinned official-source downloader and isolated tests without changing pipeline semantics.
- Include compact historical evidence rather than raw files, local paths, model binaries or logs.
- The original Windows host used Hadoop 3.3.5 native support; document this prerequisite explicitly.
