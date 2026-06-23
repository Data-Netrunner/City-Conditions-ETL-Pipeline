-- Combined daily KPIs: Weather + Air Quality (last 30 days, location_id = 1)
WITH daily_weather AS (
  SELECT
    DATE(ts)             AS day,
    location_id,
    AVG(temperature_c)   AS avg_temp_c,
    MAX(temperature_c)   AS max_temp_c,
    SUM(precipitation_mm)AS total_precip_mm,
    AVG(windspeed_kmh)   AS avg_windspeed_kmh,
    MAX(windspeed_kmh)   AS max_windspeed_kmh
  FROM fact_weather_hourly
  GROUP BY 1, 2
),
daily_aq AS (
  SELECT
    DATE(ts)   AS day,
    location_id,
    AVG(pm25)  AS pm25_avg,
    MAX(pm25)  AS pm25_peak,
    AVG(pm10)  AS pm10_avg,
    MAX(pm10)  AS pm10_peak,
    AVG(no2)   AS no2_avg,
    MAX(no2)   AS no2_peak,
    AVG(o3)    AS o3_avg,
    MAX(o3)    AS o3_peak
  FROM fact_air_quality_hourly
  GROUP BY 1, 2
)
SELECT
  w.day,
  w.location_id,
  w.avg_temp_c,
  w.max_temp_c,
  w.total_precip_mm,
  w.avg_windspeed_kmh,
  w.max_windspeed_kmh,
  a.pm25_avg,
  a.pm25_peak,
  a.pm10_avg,
  a.pm10_peak,
  a.no2_avg,
  a.no2_peak,
  a.o3_avg,
  a.o3_peak
FROM daily_weather w
LEFT JOIN daily_aq a
  ON  w.day         = a.day
  AND w.location_id = a.location_id
ORDER BY w.day DESC
LIMIT 30;
