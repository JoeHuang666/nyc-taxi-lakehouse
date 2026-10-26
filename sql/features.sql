SELECT zone_id, hour_key,
       lag(trip_count, 1) OVER w AS lag_1,
       lag(trip_count, 2) OVER w AS lag_2,
       lag(trip_count, 24) OVER w AS lag_24,
       lag(trip_count, 168) OVER w AS lag_168,
       avg(trip_count) OVER (PARTITION BY zone_id ORDER BY hour_key ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS rolling_3,
       avg(trip_count) OVER (PARTITION BY zone_id ORDER BY hour_key ROWS BETWEEN 24 PRECEDING AND 1 PRECEDING) AS rolling_24,
       avg(trip_count) OVER (PARTITION BY zone_id ORDER BY hour_key ROWS BETWEEN 168 PRECEDING AND 1 PRECEDING) AS rolling_168
FROM selected_hourly
WINDOW w AS (PARTITION BY zone_id ORDER BY hour_key)
