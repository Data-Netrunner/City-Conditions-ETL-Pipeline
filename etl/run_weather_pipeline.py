import os
import pandas as pd
import duckdb

from etl.config import CITY, LAT, LON, TIMEZONE, RAW_WEATHER_CSV
from etl.extract_weather import fetch_weather_hourly
from etl.transform_weather import clean_weather
from etl.load_weather_duckdb import init_db, upsert_location, upsert_weather
from etl.update_readme_weather import update_readme

DB_PATH = "warehouse/city_conditions.duckdb"
SCHEMA_SQL = "sql/schema.sql"
KPI_SQL = "sql/kpis_weather.sql"
KPI_OUT = "reports/latest_kpis.csv"

def main():
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("warehouse", exist_ok=True)
    os.makedirs("reports/charts", exist_ok=True)

    # Extract
    df_raw = fetch_weather_hourly(LAT, LON, TIMEZONE, past_days=7)
    df_raw.to_csv(RAW_WEATHER_CSV, index=False)

    # Transform
    df_clean = clean_weather(df_raw)

    # Load
    init_db(DB_PATH, SCHEMA_SQL)
    upsert_location(DB_PATH, 1, CITY, LAT, LON, TIMEZONE)
    upsert_weather(DB_PATH, df_clean, location_id=1)

    # KPIs
    con = duckdb.connect(DB_PATH)
    with open(KPI_SQL, "r", encoding="utf-8") as f:
        sql = f.read()
    df_kpis = con.execute(sql).df()
    con.close()

    os.makedirs("reports", exist_ok=True)
    df_kpis.to_csv(KPI_OUT, index=False)

    # Update README
    update_readme("README.md", KPI_OUT)

    print("Weather pipeline complete.")

if __name__ == "__main__":
    main()
