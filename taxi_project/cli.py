from __future__ import annotations
import argparse
import os
import time
import traceback
import uuid
from pathlib import Path
from .common import ROOT, config, dependency_hash, environment, json_write, now, read_json, writer_lock
from .ingest import ingest

def main():
    parser = argparse.ArgumentParser(description="NYC Taxi historical lakehouse")
    parser.add_argument("command", choices=["doctor", "ingest", "build", "run", "resume", "train", "backtest", "publish"])
    parser.add_argument("--profile", choices=["sample", "full"], default="full")
    parser.add_argument("--source-dir", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--run-id")
    parser.add_argument("--force-build", action="store_true")
    args = parser.parse_args()
    cfg = config()
    with writer_lock():
        if args.command == "doctor":
            from .spark_session import start, write_delta, read_delta
            spark = start(cfg)
            try:
                p = ROOT / ".runtime" / f"doctor-{uuid.uuid4().hex[:8]}"
                v = write_delta(spark.range(3), p)
                assert read_delta(spark, p, v).count() == 3
                report = {"environment": environment(), "sql": spark.sql("select 1+1").first()[0],
                          "delta_count": 3, "status": "SUCCESS"}
                json_write(ROOT / "reports/doctor.json", report)
                print(report)
            finally:
                spark.stop()
            return
        sources = ingest(args.source_dir, cfg["months"])
        if args.command == "ingest":
            print("Sources verified and imported")
            return
        fingerprint, deps = dependency_hash(sources, cfg)
        if args.command in ["train", "backtest", "publish", "resume"] and not args.run_id:
            parser.error("--run-id is required")
        if args.run_id:
            if Path(args.run_id).name != args.run_id:
                raise ValueError("Invalid run ID")
            previous_dir = ROOT / "runs" / args.run_id
            old = read_json(previous_dir / "manifest.json")
            if old["dependency_hash"] != fingerprint:
                raise ValueError("Dependencies changed; use a fresh run to rebuild.")
            if old["profile"] != args.profile:
                raise ValueError("Profile mismatch")
        else:
            previous_dir = None
        run_id = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        run_dir = ROOT / "runs" / run_id
        run_dir.mkdir(parents=True)
        manifest = {"run_id": run_id, "profile": args.profile, "started_at_utc": now(),
            "status": "RUNNING", "dependency_hash": fingerprint, "dependencies": deps,
            "environment": environment(), "stages": {}, "resumed_from": args.run_id}
        json_write(run_dir / "manifest.json", manifest)
        spark = None
        begin = time.perf_counter()
        try:
            from .spark_session import start
            from .lakehouse import build
            spark = start(cfg)
            cached = previous_dir / "build.json" if previous_dir else None
            t = time.perf_counter()
            if cached and cached.exists() and not args.force_build:
                from .spark_session import read_delta
                built = read_json(cached)
                for name, version in built["versions"].items():
                    read_delta(spark, Path(built["lake"]) / name, version).limit(1).count()
                json_write(run_dir / "build.json", built)
                manifest["stages"]["build"] = {"reused_from": args.run_id, "status": "SUCCESS"}
            else:
                built = build(spark, sources, cfg, args.profile, run_dir)
                manifest["stages"]["build"] = {"seconds": time.perf_counter()-t, "status": "SUCCESS"}
            manifest["output_table_versions"] = built["versions"]
            json_write(run_dir / "manifest.json", manifest)
            if args.profile == "sample" or args.command == "build":
                manifest["status"] = "SUCCESS"
                return
            from .features import build_features
            t = time.perf_counter()
            feature_info = build_features(spark, built, run_dir)
            manifest["stages"]["features"] = {"seconds": time.perf_counter()-t, **feature_info, "status": "SUCCESS"}
            json_write(run_dir / "manifest.json", manifest)
            from .model import train_and_replay
            t = time.perf_counter()
            trained = train_and_replay(run_dir, built, cfg, fingerprint)
            manifest["stages"]["model"] = {"seconds": time.perf_counter()-t, "model_id": trained["model_id"], "status": "SUCCESS"}
            from .publish import publish
            t = time.perf_counter()
            release = publish(spark, built, trained, run_dir, manifest)
            manifest["stages"]["publish"] = {"seconds": time.perf_counter()-t, "release": str(release), "status": "SUCCESS"}
            manifest["status"] = "SUCCESS"
        except Exception as exc:
            manifest["status"] = "FAILED"
            manifest["error"] = str(exc)
            manifest["traceback"] = traceback.format_exc()
            raise
        finally:
            manifest["ended_at_utc"] = now()
            manifest["duration_seconds"] = time.perf_counter()-begin
            json_write(run_dir / "manifest.json", manifest)
            print(f"RUN {run_id}: {manifest['status']}", flush=True)
            if spark:
                spark.stop()

if __name__ == "__main__":
    main()
