SELECT zone_id, local_date, count(*) AS trip_count,
       sum(CASE WHEN fare_eligible THEN 1 ELSE 0 END) AS fare_eligible_count,
       sum(CASE WHEN fare_eligible THEN recorded_total_amount ELSE 0 END) AS recorded_total_amount_sum
FROM silver_trips
GROUP BY zone_id, local_date
