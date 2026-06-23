-- Daily KPI summary from hourly weather only (kept for reference / ad-hoc queries)
SELECT
  DATE(ts)              AS day,
  location_id,
  AVG(temperature_c)    AS avg_temp_c,
  MAX(temperature_c)    AS max_temp_c,
  SUM(precipitation_mm) AS total_precip_mm,
  AVG(windspeed_kmh)    AS avg_windspeed_kmh,
  MAX(windspeed_kmh)    AS max_windspeed_kmh
FROM fact_weather_hourly
GROUP BY 1, 2
ORDER BY day DESC
LIMIT 30;
