from __future__ import annotations
import contextlib
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
from datetime import datetime, timezone
import yaml

ROOT = Path(__file__).resolve().parents[1]

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def json_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(temporary, path)

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def config():
    cfg = yaml.safe_load((ROOT / "config/project.yaml").read_text(encoding="utf-8"))
    if cfg["months"] != ["2024-01", "2024-02", "2024-03"] or cfg["timezone"] != "America/New_York":
        raise ValueError("v1 supports NYC 2024 Q1 only; extend DST and split tests before changing range.")
    return cfg

def environment():
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": {p: importlib.metadata.version(p) for p in
                         ["pyspark", "delta-spark", "pandas", "pyarrow", "numpy", "scikit-learn", "tzdata"]}}

def dependency_hash(source_manifest, cfg):
    files = sorted((ROOT / "taxi_project").glob("*.py")) + sorted((ROOT / "sql").glob("*.sql"))
    payload = {"sources": {k: v["sha256"] for k,v in source_manifest.items()},
               "config": cfg, "code": {str(p.relative_to(ROOT)): digest(p) for p in files},
               "environment": environment()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(), payload

@contextlib.contextmanager
def writer_lock(root=ROOT):
    lock = Path(root) / ".writer.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, json.dumps({"pid": os.getpid(), "started": now()}).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)

def promote(release, root=ROOT):
    release = Path(release)
    if not (release / "release_manifest.json").is_file():
        raise ValueError("Release is incomplete")
    manifest = read_json(release / "release_manifest.json")
    if manifest["status"] != "SUCCESS":
        raise ValueError("Only successful releases can be promoted")
    for name, checksum in manifest["files"].items():
        if digest(release / name) != checksum:
            raise ValueError(f"Release checksum mismatch: {name}")
    json_write(Path(root) / "current_release.json", {"release_id": release.name, "path": str(release)})
