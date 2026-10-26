# Installation and platform notes

## Prerequisites

- Python 3.11, available from [Python](https://www.python.org/downloads/).
- A Java 17 JDK, for example [Eclipse Temurin](https://adoptium.net/temurin/releases/?version=17).
- Git, if cloning, from [Git](https://git-scm.com/downloads).
- Optional Windows Power BI Desktop from [Microsoft](https://www.microsoft.com/download/details.aspx?id=58494).
- Network access for Python packages, the initial Delta JAR resolution, and source downloads.

No account credentials are used by the pipeline. Power BI Desktop is optional for Python
reports and tests. macOS/Linux users can run the Python workflow but need Windows for Desktop.
Cross-platform commands are provided; the original full workload was validated only on Windows.

## Environment

Create and activate a Python 3.11 virtual environment as shown in the root README, then run:

```sh
python --version
java -version
python -m pip install -r requirements.txt
python -m pytest -q
python -m taxi_project doctor
```

Set `JAVA_HOME` to the JDK directory, not its `bin` subdirectory. Reopen the terminal after
changing system environment variables. `requirements.txt` pins direct dependencies from the
working environment. `requirements.lock.txt` is the complete observed package inventory,
not a universal or hash-locked dependency resolution. A fresh environment installation has
not yet been independently validated. Do not silently replace unavailable versions and
claim exact reproduction; record any replacements and rerun the tests.

The repository is a source checkout. Its configuration and SQL are resolved relative to
the checkout, so run commands there rather than installing a wheel elsewhere.

## Windows native Hadoop prerequisite

The original successful Windows host had **Hadoop 3.3.5 native support configured through
`HADOOP_HOME`**, in addition to Java 17. The Python requirements do not install those native
binaries. Their original build provenance is not recorded in this repository, so they are
not redistributed and no third-party executable mirror is prescribed.

Use compatible, trusted native libraries provided by your environment, or build them
from the matching Apache Hadoop source. If you do not have these, an Ubuntu/WSL environment
is an alternative to evaluate, not a validated equivalent of the original host run.
Run `doctor` and the Spark fixture before the full dataset on any new environment.
Do not work around an AccessDenied error by granting broad filesystem permissions.

## Downloads

```sh
python tools/download_data.py --output downloads
```

The downloader reads four fixed official URLs from `config/sources.json`, checks file size
and SHA-256, and moves a completed temporary file into place only after validation.
An existing valid file is reused. A mismatched existing file is preserved and raises an
error; use a new output directory to investigate. Run only one downloader per output directory at a time. An upstream revision will fail the
pinned checksum rather than silently change the experiment.

You may instead download the four files manually from the URLs in the manifest. Keep their
original names, then use `--source-dir YOUR_DIRECTORY` for both sample and full runs.
The original source download timestamp is unknown; `imported_at_utc` records ingestion time.

## Troubleshooting

| Symptom | Action |
|---|---|
| PowerShell blocks activation | Use `.venv\Scripts\python.exe` directly or activate from Command Prompt |
| Java missing or wrong version | Correct `JAVA_HOME` and `PATH`; check `java -version` |
| Delta JAR resolution fails | Check network/proxy configuration; optionally set `TAXI_IVY_CACHE` to a trusted populated cache |
| Hadoop NativeIO / winutils error | Check compatible native prerequisites; do not download arbitrary executable fixes |
| `_delta_log` AccessDenied in a sandbox | Retry the smoke check in an ordinary host terminal with normal project access |
| Spark fails to bind localhost | Check localhost access and firewall policy for the chosen JDK |
| Shutdown temporary JAR warning | Check run status and evidence; the original host had successful outputs plus this unresolved cleanup warning |
| Existing `.writer.lock` | Confirm the recorded process has stopped before manually removing this one lock |

The configuration uses four local workers, a 6 GB driver heap and 16 shuffle partitions.
This was exercised on a 32 GB machine; no lower-memory minimum is claimed. Reruns retain
Delta history and raw snapshots, so disk use grows over time.
