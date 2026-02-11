import duckdb
import pandas as pd

def init_db(db_path: str, schema_sql_path: str) -> None:
    con = duckdb.connect(db_path)
    with open(schema_sql_path, "r", encoding="utf-8") as f:
        con.execute(f.read())
    con.close()

def upsert_location(db_path: str, location_id: int, city: str, lat: float, lon: float, timezone: str) -> None:
    con = duckdb.connect(db_path)
    con.execute("""
        INSERT INTO dim_location(location_id, city, lat, lon, timezone)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(location_id) DO UPDATE SET
          city=excluded.city,
          lat=excluded.lat,
          lon=excluded.lon,
          timezone=excluded.timezone
    """, [location_id, city, lat, lon, timezone])
    con.close()

def upsert_weather(db_path: str, df_weather: pd.DataFrame, location_id: int = 1) -> None:
    con = duckdb.connect(db_path)

    df = df_weather.copy()
    df["location_id"] = location_id

    con.register("w", df)
    con.execute("""
        INSERT INTO fact_weather_hourly(location_id, ts, temperature_c, precipitation_mm, windspeed_kmh)
        SELECT location_id, ts, temperature_c, precipitation_mm, windspeed_kmh FROM w
        ON CONFLICT(location_id, ts) DO UPDATE SET
          temperature_c=excluded.temperature_c,
          precipitation_mm=excluded.precipitation_mm,
          windspeed_kmh=excluded.windspeed_kmh
    """)
    con.close()
