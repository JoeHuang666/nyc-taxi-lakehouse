"""Host-side Spark integration checks; isolated fixtures, never modifies business tables."""
import uuid
from datetime import datetime
from pathlib import Path
import pytest
from pyspark.sql import functions as F
from taxi_project.common import ROOT, config
from taxi_project.spark_session import start, write_delta, read_delta
from taxi_project.lakehouse import clean

@pytest.fixture(scope="module")
def spark():
    s = start(config())
    yield s
    s.stop()

@pytest.mark.spark
def test_cleanup_dst_and_duplicate_multiplicity(spark):
    zones = spark.createDataFrame([(1,"Test","Manhattan","Yellow",True)],
                                 ["zone_id","zone_name","borough","service_zone","is_nyc_zone"])
    schema = "tpep_pickup_datetime string, tpep_dropoff_datetime string, PULocationID int, total_amount double, passenger_count double, trip_distance double, source_month string"
    good = (datetime(2024,3,10,1,30),datetime(2024,3,10,1,40),1,-5.,1.,1.,"2024-03")
    rows = [good,good,
        (datetime(2024,3,10,3,30),datetime(2024,3,10,3,40),1,10.,None,1.,"2024-03"),
        (datetime(2024,3,10,2,30),datetime(2024,3,10,3,40),1,10.,1.,1.,"2024-03"),
        (datetime(2024,4,1),datetime(2024,4,1,1),1,10.,1.,1.,"2024-03"),
        (datetime(2024,3,1),datetime(2024,3,1,1),999,10.,1.,1.,"2024-03")]
    # Python naive datetime conversion uses the host timezone; source Parquet stores wall-clock values.
    rows = [(r[0].isoformat(sep=" "), r[1].isoformat(sep=" "), *r[2:]) for r in rows]
    raw = (spark.createDataFrame(rows,schema)
           .withColumn("tpep_pickup_datetime", F.col("tpep_pickup_datetime").cast("timestamp"))
           .withColumn("tpep_dropoff_datetime", F.col("tpep_dropoff_datetime").cast("timestamp")))
    assert raw.select(F.date_format("tpep_pickup_datetime", "yyyy-MM-dd HH:mm")).first()[0] == "2024-03-10 01:30"
    valid,bad = clean(raw,zones)
    assert raw.count() == valid.count()+bad.count() == 6
    assert valid.count() == 3 and bad.count() == 3
    assert valid.filter("negative_fare").count() == 2
    assert valid.filter("fare_eligible").count() == 1
    times={r[0] for r in valid.select(F.date_format("pickup_utc","yyyy-MM-dd HH:mm")).collect()}
    assert times == {"2024-03-10 06:30","2024-03-10 07:30"}
    assert {r.primary_reason for r in bad.collect()} == {"outside_source_month","nonexistent_local_time","invalid_nyc_zone"}
    path=ROOT / ".runtime" / f"integration-{uuid.uuid4().hex}"
    first=write_delta(valid,path,"2024-03")
    before=read_delta(spark,path,first)
    for _ in range(2):
        latest=write_delta(valid,path,"2024-03")
        after=read_delta(spark,path,latest)
        assert after.count()==3
        assert before.exceptAll(after).count()==0
        assert after.exceptAll(before).count()==0
    assert read_delta(spark,path,first).count()==3

