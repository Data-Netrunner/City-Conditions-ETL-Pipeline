# City Conditions ETL Pipeline

A fully automated end-to-end ETL pipeline that pulls daily weather and air quality data for **Toronto, Canada**, loads it into a DuckDB analytics warehouse, and publishes KPI reports and charts updated every day via GitHub Actions.

---

## Data Sources

All data is pulled from **[Open-Meteo](https://open-meteo.com/)** — a free, open-source weather and air quality API requiring no API key.

| Source | API | Data Collected |
|---|---|---|
| Weather | [Open-Meteo Forecast API](https://api.open-meteo.com/v1/forecast) | Temperature (C), Precipitation (mm), Wind Speed (km/h) |
| Air Quality | [Open-Meteo Air Quality API](https://air-quality-api.open-meteo.com/v1/air-quality) | PM2.5, PM10, NO2, Ozone |

---

## Latest KPI Snapshot

- Date: **2026-08-23**
- Avg Temp (C): **17.44**
- Max Temp (C): **19.4**
- Total Precip (mm): **10.9**
- Avg Wind (km/h): **11.59**
- Max Wind (km/h): **19.8**
- PM2.5 Avg (ug/m3): **3.65**
- PM2.5 Peak (ug/m3): **8.9**

---

## Next-Day Forecast (model output)

- Forecast for **2026-08-24**: **40.07 °C** average temperature
- Persistence baseline ("same as today"): 17.44 °C
- Model: RidgeCV on 10 engineered features, trained on 21 observed days

### Accuracy (walk-forward backtest)

Every forecast below was made using only data available *before* the day it predicts — no future information leaks into training.

| Metric | Model | Persistence baseline |
|---|---|---|
| MAE (°C) | **1.419** | 1.231 |
| RMSE (°C) | **1.488** | 1.609 |
| Days scored | 6 | 6 |

**Skill score vs persistence: -15.3%** — currently not yet beating the baseline. Skill is the share of the baseline's error the model removes; it is published whether it is positive or negative.

![Forecast vs Actual](reports/charts/forecast_vs_actual_30d.png)

![Forecast Error](reports/charts/forecast_error_30d.png)

---

## Charts (auto-updated daily)

### Weather

- **Average Temperature (C):** daily mean temperature

![Average Temperature (30d)](reports/charts/avg_temp_30d.png)

- **Total Precipitation (mm):** total precipitation per day

![Daily Precipitation (30d)](reports/charts/precip_30d.png)

### Air Quality

- **PM2.5 (ug/m3):** daily average fine particulate concentration (smaller = cleaner air)

![PM2.5 Average (30d)](reports/charts/pm25_avg_30d.png)

---

## How It Works

| Step | What happens |
|---|---|
| Extract | Pulls 7 days of hourly weather and air quality data from Open-Meteo |
| Transform | Cleans and validates the data |
| Load | Upserts into a DuckDB warehouse |
| Report | Generates KPI CSV, 30-day charts, and rewrites this README |
| Log | Appends a row to reports/run_log.csv |

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | ETL scripting |
| DuckDB | Analytics warehouse |
| pandas | Data transformation |
| requests | API extraction |
| matplotlib | Chart generation |
| GitHub Actions | Daily automation |

---

## Outputs

- `warehouse/city_conditions.duckdb` — full historical warehouse
- `reports/latest_kpis.csv` — most recent daily KPI snapshot
- `reports/run_log.csv` — log of every pipeline run
- `reports/charts/*.png` — auto-generated 30-day charts

---

## How to Run Locally

```bash
git clone https://github.com/Data-Netrunner/City-Conditions-ETL-Pipeline.git
cd City-Conditions-ETL-Pipeline
pip install -r requirements.txt
python etl/run_weather_pipeline.py
```

No API keys or paid services required.

---

*Built by Andre Felix - Data updated daily via GitHub Actions*
