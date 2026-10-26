from __future__ import annotations
import pandas as pd
from pyspark.sql import functions as F
from .common import ROOT, json_write
from .spark_session import write_delta, read_delta

NYC = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]

def calendar():
    utc = pd.date_range("2024-01-01", "2024-04-01", tz="America/New_York", freq="h", inclusive="left").tz_convert("UTC")
    local = utc.tz_convert("America/New_York")
    return pd.DataFrame({"hour_key": utc.asi8 // 10**9 // 3600,
        "hour_start_utc": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "local_date": local.strftime("%Y-%m-%d"), "local_hour": local.hour,
        "weekday": local.dayofweek, "weekend": (local.dayofweek >= 5).astype(int),
        "utc_offset": [int(t.utcoffset().total_seconds() / 3600) for t in local],
        "source_month": local.strftime("%Y-%m")})

def zone_frame(spark, source):
    return (spark.read.option("header", True).csv(source).select(
        F.col("LocationID").cast("int").alias("zone_id"), F.col("Zone").alias("zone_name"),
        F.col("Borough").alias("borough"), F.col("service_zone"))
        .withColumn("is_nyc_zone", F.col("borough").isin(NYC)))

def clean(bronze, zones):
    df = (bronze.withColumn("pickup_local", F.col("tpep_pickup_datetime").cast("timestamp"))
          .withColumn("pickup_utc", F.to_utc_timestamp("pickup_local", "America/New_York"))
          .withColumn("zone_id", F.col("PULocationID").cast("int"))
          .join(F.broadcast(zones), "zone_id", "left"))
    reasons = [
        F.when(F.col("pickup_local").isNull(), F.lit("invalid_pickup")),
        F.when(F.from_utc_timestamp("pickup_utc", "America/New_York") != F.col("pickup_local"), F.lit("nonexistent_local_time")),
        F.when(F.date_format("pickup_local", "yyyy-MM") != F.col("source_month"), F.lit("outside_source_month")),
        F.when(~F.coalesce(F.col("is_nyc_zone"), F.lit(False)), F.lit("invalid_nyc_zone"))]
    df = df.withColumn("all_reasons", F.filter(F.array(*reasons), lambda r: r.isNotNull()))
    amount = F.col("total_amount").cast("double")
    df = (df.withColumn("primary_reason", F.element_at("all_reasons", 1))
          .withColumn("hour_key", F.floor(F.col("pickup_utc").cast("long") / 3600).cast("long"))
          .withColumn("local_date", F.date_format("pickup_local", "yyyy-MM-dd"))
          .withColumn("recorded_total_amount", F.col("total_amount").cast("decimal(18,2)"))
          .withColumn("fare_eligible", F.coalesce((amount >= 0) & (amount < float("inf")) &
                      ~F.isnan(amount) & F.col("recorded_total_amount").isNotNull(), F.lit(False)))
          .withColumn("negative_fare", F.coalesce(amount < 0, F.lit(False)))
          .withColumn("missing_passengers", F.col("passenger_count").isNull())
          .withColumn("invalid_distance", F.coalesce(F.col("trip_distance") <= 0, F.lit(True)))
          .withColumn("invalid_dropoff", F.coalesce(
              F.col("tpep_dropoff_datetime") < F.col("pickup_local"), F.lit(True))))
    return df.filter(F.size("all_reasons") == 0), df.filter(F.size("all_reasons") > 0)

def build(spark, sources, cfg, profile, run_dir):
    lake = ROOT / "data/lakehouse" / profile
    zones = zone_frame(spark, sources["taxi_zone_lookup.csv"]["path"])
    if zones.count() != zones.select("zone_id").distinct().count():
        raise ValueError("Zone join would multiply rows")
    versions = {"dim_zone": write_delta(zones, lake / "dim_zone")}
    quality = []
    for month in cfg["months"]:
        src = sources[f"yellow_tripdata_{month}.parquet"]
        raw = spark.read.parquet(src["path"])
        if profile == "sample":
            raw = raw.limit(cfg["sample_rows"])
        expected = src["row_count"] if profile == "full" else min(src["row_count"], cfg["sample_rows"])
        bronze = (raw.withColumn("source_month", F.lit(month))
                  .withColumn("source_sha256", F.lit(src["sha256"]))
                  .withColumn("ingested_at_utc", F.current_timestamp()))
        versions["bronze"] = write_delta(bronze, lake / "bronze", month)
        bronze = read_delta(spark, lake / "bronze", versions["bronze"]).filter(F.col("source_month") == month)
        count = bronze.count()
        if count != expected:
            raise ValueError("Raw/Bronze conservation failed")
        valid, quarantine = clean(bronze, zones)
        valid.persist()
        quarantine.persist()
        try:
            n_valid, n_bad = valid.count(), quarantine.count()
            if n_valid + n_bad != count:
                raise ValueError("Silver/quarantine conservation failed")
            if n_bad / count > cfg["quarantine_limit"]:
                raise ValueError(f"REVIEW: quarantine exceeds limit: {month} {n_bad}/{count}")
            versions["silver"] = write_delta(valid, lake / "silver", month)
            versions["quarantine"] = write_delta(quarantine, lake / "quarantine", month)
            flags = valid.agg(*[F.sum(F.col(c).cast("long")).alias(c) for c in
                               ["negative_fare", "missing_passengers", "invalid_distance", "invalid_dropoff"]]).first().asDict()
            # Preserve row multiplicities; this is a diagnostic, never a deletion rule.
            from .ingest import COLUMNS
            duplicates = count - bronze.select(*COLUMNS).distinct().count()
            reasons = {r["primary_reason"]: r["count"] for r in quarantine.groupBy("primary_reason").count().collect()}
            quality.append({"source_month": month, "raw_count": count, "silver_count": n_valid,
                "quarantine_count": n_bad, "quarantine_rate": n_bad/count,
                "identical_extra_rows": duplicates, "reasons": reasons, **flags})
            print(f"MONTH {month}: raw={count:,}, valid={n_valid:,}, quarantine={n_bad:,}", flush=True)
        finally:
            valid.unpersist()
            quarantine.unpersist()
    silver = read_delta(spark, lake / "silver", versions["silver"])
    silver.createOrReplaceTempView("silver_trips")
    hourly = spark.sql((ROOT / "sql/zone_hourly.sql").read_text())
    daily = spark.sql((ROOT / "sql/zone_daily.sql").read_text())
    if hourly.agg(F.sum("trip_count")).first()[0] != sum(q["silver_count"] for q in quality):
        raise ValueError("Gold/Silver conservation failed")
    cal = calendar()
    cal_spark = spark.createDataFrame(cal.to_dict("records"))
    grid = zones.filter("is_nyc_zone").select("zone_id").crossJoin(cal_spark.select("hour_key", "source_month"))
    if profile == "full":
        observed = {r[0] for r in hourly.select("hour_key").distinct().collect()}
        if observed != set(cal.hour_key):
            raise ValueError("REVIEW: city-wide empty hours; do not turn missing hours into zeros")
    dense = (grid.join(hourly.drop("source_month"), ["zone_id", "hour_key"], "left")
             .fillna({"trip_count": 0}).withColumn("source_covered", F.lit(profile == "full")))
    versions["gold_hourly"] = write_delta(dense, lake / "gold_hourly")
    versions["gold_daily"] = write_delta(daily, lake / "gold_daily")
    versions["dim_hour"] = write_delta(cal_spark, lake / "dim_hour")
    ranked = (hourly.filter(F.col("source_month") == "2024-01").groupBy("zone_id")
              .agg(F.sum("trip_count").alias("january_count"))
              .orderBy(F.desc("january_count"), "zone_id").limit(cfg["top_zones"]).collect())
    selected = [r.asDict() for r in ranked]
    if len(selected) != cfg["top_zones"]:
        raise ValueError("Too few zones")
    result = {"versions": versions, "lake": str(lake), "quality": quality, "selected_zones": selected}
    json_write(run_dir / "build.json", result)
    return result
