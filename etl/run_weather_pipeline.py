import os
import duckdb

from etl.config import CITY, LAT, LON, TIMEZONE, RAW_WEATHER_CSV
from etl.extract_weather import fetch_weather_hourly
from etl.transform_weather import clean_weather
from etl.load_weather_duckdb import init_db, upsert_location, upsert_weather
from etl.update_readme_weather import update_readme

from etl.extract_openaq import fetch_air_quality_hourly
from etl.transform_air_quality import clean_air_quality
from etl.load_air_quality_duckdb import upsert_air_quality

from etl.make_charts_combined import make_charts

DB_PATH = "warehouse/city_conditions.duckdb"
SCHEMA_SQL = "sql/schema.sql"
KPI_SQL_COMBINED = "sql/kpis_combined.sql"
KPI_OUT = "reports/latest_kpis.csv"

def main():
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("warehouse", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    os.makedirs("reports/charts", exist_ok=True)

    # Schema + location
    init_db(DB_PATH, SCHEMA_SQL)
    upsert_location(DB_PATH, 1, CITY, LAT, LON, TIMEZONE)

    # Weather ETL
    df_weather_raw = fetch_weather_hourly(LAT, LON, TIMEZONE, past_days=7)
    df_weather_raw.to_csv(RAW_WEATHER_CSV, index=False)
    df_weather = clean_weather(df_weather_raw)
    upsert_weather(DB_PATH, df_weather, location_id=1)

    # Air Quality ETL
    df_aq_raw = fetch_air_quality_hourly(LAT, LON, TIMEZONE, past_days=7)
    df_aq = clean_air_quality(df_aq_raw)
    upsert_air_quality(DB_PATH, df_aq, location_id=1)

    # Combined KPIs
    con = duckdb.connect(DB_PATH)
    with open(KPI_SQL_COMBINED, "r", encoding="utf-8") as f:
        sql = f.read()
    df_kpis = con.execute(sql).df()
    con.close()
    df_kpis.to_csv(KPI_OUT, index=False)

    # Charts + README
    make_charts(KPI_OUT, "reports/charts")
    update_readme("README.md", KPI_OUT)

    print("Pipeline complete (Weather + Air Quality + Charts).")

if __name__ == "__main__":
    main()
