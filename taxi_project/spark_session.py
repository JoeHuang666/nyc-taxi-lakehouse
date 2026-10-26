from __future__ import annotations
import os
import sys
from pathlib import Path
from .common import ROOT

def start(cfg):
    import tempfile
    temp = ROOT / ".runtime" / "tmp"
    temp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = str(temp)
    tempfile.tempdir = str(temp)
    from pyspark.sql import SparkSession
    from delta import configure_spark_with_delta_pip
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    os.environ["SPARK_LOCAL_IP"] = "127.0.0.1"
    local = ROOT / ".runtime" / "spark"
    local.mkdir(parents=True, exist_ok=True)
    # Native Windows path avoids Spark treating C:/... as a URI scheme.
    builder = (SparkSession.builder.master(cfg["spark"]["master"]).appName("NYCTaxiLakehouse")
        .config("spark.driver.memory", cfg["spark"]["driver_memory"])
        .config("spark.driver.host", "127.0.0.1").config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", str(cfg["spark"]["shuffle_partitions"]))
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.execution.arrow.pyspark.enabled", "false")
        .config("spark.sql.parquet.inferTimestampNTZ.enabled", "false")
        .config("spark.local.dir", str(local))
        .config("spark.sql.warehouse.dir", (ROOT / ".runtime/warehouse").as_uri())
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"))
    cache = os.environ.get("TAXI_IVY_CACHE")
    if cache:
        builder = builder.config("spark.jars.ivy", cache)
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark

def write_delta(df, path, month=None):
    from delta.tables import DeltaTable
    path = Path(path).as_posix()
    writer = df.write.format("delta").mode("overwrite")
    if month is not None:
        writer = writer.partitionBy("source_month").option("replaceWhere", f"source_month = '{month}'")
    else:
        writer = writer.option("overwriteSchema", "true")
    writer.save(path)
    return int(DeltaTable.forPath(df.sparkSession, path).history(1).first()["version"])

def read_delta(spark, path, version):
    return spark.read.format("delta").option("versionAsOf", version).load(Path(path).as_posix())

