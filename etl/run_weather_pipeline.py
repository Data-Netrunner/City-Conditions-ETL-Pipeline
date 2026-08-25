import os

import matplotlib
matplotlib.use("Agg")  # Must be set before any other matplotlib import (no display in GitHub Actions)

import duckdb

from etl.config import CITY, LAT, LON, TIMEZONE, RAW_WEATHER_CSV
from etl.extract_weather import fetch_weather_hourly
from etl.transform_weather import clean_weather
from etl.load_weather_duckdb import init_db, upsert_location, upsert_weather
from etl.extract_openaq import fetch_air_quality_hourly
from etl.transform_air_quality import clean_air_quality
from etl.load_air_quality_duckdb import upsert_air_quality
from etl.make_charts_combined import make_charts
from etl.update_readme_weather import update_readme
from etl.data_quality import assert_required_columns, assert_not_empty, append_run_log

# --- prediction section ---
from etl.history_store import append_daily_history
from etl.predict_temperature import predict_next_day
from etl.make_prediction_chart import make_prediction_charts

DB_PATH    = "warehouse/city_conditions.duckdb"
SCHEMA_SQL = "sql/schema.sql"
KPI_SQL    = "sql/kpis_combined.sql"
KPI_OUT    = "reports/latest_kpis.csv"


def main() -> None:
    weather_rows = 0
    aq_rows      = 0
    kpi_rows     = 0
    prediction   = None

    try:
        os.makedirs("data/raw",       exist_ok=True)
        os.makedirs("data/history",   exist_ok=True)
        os.makedirs("warehouse",      exist_ok=True)
        os.makedirs("reports",        exist_ok=True)
        os.makedirs("reports/charts", exist_ok=True)

        # 0) Schema + location seed
        init_db(DB_PATH, SCHEMA_SQL)
        upsert_location(DB_PATH, 1, CITY, LAT, LON, TIMEZONE)

        # 1) Weather: Extract -> Transform -> Load
        #    forecast_days=0 keeps Open-Meteo's forecast rows OUT of the
        #    observations table (see etl/extract_weather.py for why).
        df_weather_raw = fetch_weather_hourly(
            LAT, LON, TIMEZONE, past_days=7, forecast_days=0
        )
        assert_required_columns(
            df_weather_raw,
            ["ts", "temperature_c", "precipitation_mm", "windspeed_kmh"],
            "weather_raw",
        )
        df_weather_raw.to_csv(RAW_WEATHER_CSV, index=False)

        df_weather = clean_weather(df_weather_raw)
        assert_not_empty(df_weather, "weather_clean")
        weather_rows = len(df_weather)
        upsert_weather(DB_PATH, df_weather, location_id=1)

        # 2) Air Quality: Extract -> Transform -> Load
        df_aq_raw = fetch_air_quality_hourly(LAT, LON, TIMEZONE, past_days=7)
        assert_required_columns(df_aq_raw, ["ts", "pm25", "pm10", "no2", "o3"], "aq_raw")

        df_aq = clean_air_quality(df_aq_raw)
        assert_not_empty(df_aq, "aq_clean")
        aq_rows = len(df_aq)
        upsert_air_quality(DB_PATH, df_aq, location_id=1)

        # 3) Combined KPIs
        con = duckdb.connect(DB_PATH)
        with open(KPI_SQL, "r", encoding="utf-8") as f:
            sql = f.read()
        df_kpis = con.execute(sql).df()
        con.close()

        assert_not_empty(df_kpis, "kpi_output")
        kpi_rows = len(df_kpis)
        df_kpis.to_csv(KPI_OUT, index=False)

        # 4) Durable history — must run BEFORE prediction, since the model
        #    trains off the accumulated file rather than the rolling warehouse.
        append_daily_history(DB_PATH, location_id=1)

        # 5) Predict tomorrow + score every past forecast walk-forward
        prediction = predict_next_day(location_id=1)

        # 6) Charts + README (README now carries the forecast + accuracy block)
        make_charts(KPI_OUT, "reports/charts")
        make_prediction_charts("reports/charts")
        update_readme("README.md", KPI_OUT, prediction=prediction)

        append_run_log(weather_rows, aq_rows, kpi_rows, status="success")
        print("Pipeline complete (Weather + Air Quality + Charts + Forecast).")

    except Exception as e:
        append_run_log(weather_rows, aq_rows, kpi_rows, status="failed", message=str(e))
        raise


if __name__ == "__main__":
    main()
