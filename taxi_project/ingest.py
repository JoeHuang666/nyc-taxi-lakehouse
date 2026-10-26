from __future__ import annotations
import csv
import hashlib
import shutil
from pathlib import Path
import pyarrow.parquet as pq
from .common import ROOT, digest, json_write, now

COLUMNS = ["VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime", "passenger_count",
           "trip_distance", "RatecodeID", "store_and_fwd_flag", "PULocationID", "DOLocationID",
           "payment_type", "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
           "improvement_surcharge", "total_amount", "congestion_surcharge", "Airport_fee"]

def ingest(source_dir, months):
    source_dir = Path(source_dir)
    result = {}
    names = [f"yellow_tripdata_{m}.parquet" for m in months] + ["taxi_zone_lookup.csv"]
    # Validate all sources before mutating the raw snapshot.
    for name in names:
        source = source_dir / name
        if not source.is_file():
            raise FileNotFoundError(f"Required source missing: {source}")
        sha = digest(source)
        if name.endswith(".parquet"):
            pf = pq.ParquetFile(source)
            if set(pf.schema_arrow.names) != set(COLUMNS):
                raise ValueError(f"Unexpected schema: {name}: {pf.schema_arrow}")
            for column in ["tpep_pickup_datetime", "tpep_dropoff_datetime"]:
                if str(pf.schema_arrow.field(column).type) != "timestamp[us]":
                    raise ValueError(f"Review timestamp semantics: {pf.schema_arrow}")
            rows, schema = pf.metadata.num_rows, str(pf.schema_arrow)
            month = name[len("yellow_tripdata_"):-8]
            url = f"https://d37ci6vzurychx.cloudfront.net/trip-data/{name}"
        else:
            with source.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                records = list(reader)
                schema = str(reader.fieldnames)
            if set(reader.fieldnames) != {"LocationID", "Borough", "Zone", "service_zone"}:
                raise ValueError("Unexpected zone schema")
            ids = [int(r["LocationID"]) for r in records]
            if len(ids) != len(set(ids)) or not ids:
                raise ValueError("Zone lookup IDs must be unique and nonempty")
            rows, month = len(records), None
            url = f"https://d37ci6vzurychx.cloudfront.net/misc/{name}"
        destination = ROOT / "data/raw" / sha / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            part = destination.with_suffix(destination.suffix + ".part")
            shutil.copyfile(source, part)
            if digest(part) != sha:
                raise ValueError("Source changed while copying")
            part.replace(destination)
        elif digest(destination) != sha:
            raise ValueError("Immutable raw snapshot has changed")
        result[name] = {"source_url": url, "imported_at_utc": now(), "retrieved_at_utc": None,
                        "retrieval_note": "User download; original retrieval time not independently known",
                        "source_month": month, "sha256": sha, "size_bytes": destination.stat().st_size,
                        "row_count": rows, "schema": schema,
                        "schema_fingerprint": hashlib.sha256(schema.encode()).hexdigest(),
                        "path": str(destination)}
    json_write(ROOT / "data/source_manifest.json", result)
    return result
