SELECT zone_id, source_month, hour_key, count(*) AS trip_count
FROM silver_trips
GROUP BY zone_id, source_month, hour_key
