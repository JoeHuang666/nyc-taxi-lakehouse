# Publishing this repository

This directory is a standalone repository. Publish its contents as the repository root,
not the parent workspace containing the original data and local experiment files.
When starting from an extracted ZIP, run `git init -b main` to initialize Git.
When cloning an existing repository, Git history and the origin remote already exist;
skip initialization and choose your own remote if publishing a separate copy.

## Review before the first commit

```sh
git status --short
git add .
git diff --cached --stat
git diff --cached
```

Confirm the staged files contain no raw data, caches, local paths or generated Power BI
files. The MIT license has been selected by the owner. Configure your own Git identity
if Git asks; this project does not supply a name or email on your behalf.

```sh
git commit -m "Add NYC taxi lakehouse and forecasting portfolio"
```

Create an empty GitHub repository using your account. Do not initialize another README
or license there. Replace `YOUR_REPOSITORY_URL` below with its actual clone URL:

```sh
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

These commands publish to the remote you choose. After pushing, review the Actions result for that commit. The workflow configuration
alone is not proof that its tests passed.

Suggested repository name: `nyc-taxi-lakehouse`.
Suggested description: "Local Spark/Delta lakehouse, leakage-tested hourly forecasting,
and reproducible Power BI reporting on NYC taxi data."
Suggested topics: `data-engineering`, `pyspark`, `delta-lake`, `sql`, `machine-learning`,
`time-series`, `powerbi`, `portfolio`.
