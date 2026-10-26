"""Download the four pinned official TLC source files using only the standard library."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def verify(path, spec):
    if path.stat().st_size != spec["size_bytes"]:
        raise ValueError(f"Size mismatch: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != spec["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {path}")


def download(name, spec, output):
    if Path(name).name != name or not spec["source_url"].startswith(
        "https://d37ci6vzurychx.cloudfront.net/"
    ):
        raise ValueError("Expected a filename and an official TLC source URL")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / name
    if destination.exists():
        verify(destination, spec)
        return destination
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output, suffix=".part", delete=False) as target:
            temporary = Path(target.name)
            with urlopen(spec["source_url"], timeout=60) as response:
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    target.write(block)
        verify(temporary, spec)
        # shortcut: one downloader per directory; add a lock before supporting concurrent runs.
        if destination.exists():
            verify(destination, spec)
        else:
            os.rename(temporary, destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "downloads")
    args = parser.parse_args()
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))
    for name, spec in sources.items():
        print(f"Verified: {download(name, spec, args.output)}", flush=True)


if __name__ == "__main__":
    main()
