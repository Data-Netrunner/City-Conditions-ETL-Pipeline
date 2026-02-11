CREATE TABLE IF NOT EXISTS dim_location (
  location_id INTEGER PRIMARY KEY,
  city VARCHAR,
  lat DOUBLE,
  lon DOUBLE,
  timezone VARCHAR
);

CREATE TABLE IF NOT EXISTS fact_weather_hourly (
  location_id INTEGER,
  ts TIMESTAMP,
  temperature_c DOUBLE,
  precipitation_mm DOUBLE,
  windspeed_kmh DOUBLE,
  PRIMARY KEY(location_id, ts)
);
