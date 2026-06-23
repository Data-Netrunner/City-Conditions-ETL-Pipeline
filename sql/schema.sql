-- City Conditions warehouse schema
-- init_db() runs this on every pipeline start; CREATE TABLE IF NOT EXISTS makes it safe to re-run.

CREATE TABLE IF NOT EXISTS dim_location (
  location_id INTEGER PRIMARY KEY,
  city        VARCHAR,
  lat         DOUBLE,
  lon         DOUBLE,
  timezone    VARCHAR
);

CREATE TABLE IF NOT EXISTS fact_weather_hourly (
  location_id      INTEGER,
  ts               TIMESTAMP,
  temperature_c    DOUBLE,
  precipitation_mm DOUBLE,
  windspeed_kmh    DOUBLE,
  PRIMARY KEY (location_id, ts)
);

CREATE TABLE IF NOT EXISTS fact_air_quality_hourly (
  location_id INTEGER,
  ts          TIMESTAMP,
  pm25        DOUBLE,
  pm10        DOUBLE,
  no2         DOUBLE,
  o3          DOUBLE,
  PRIMARY KEY (location_id, ts)
);
