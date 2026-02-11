# City Conditions ETL (Daily)

This project builds an end-to-end ETL pipeline that pulls daily-updating weather data, cleans it, loads it into a DuckDB analytics warehouse, and publishes stakeholder-ready KPIs and charts.

## Latest KPI snapshot

- Date: **2026-02-17**
- Avg Temp (°C): **0.33**
- Max Temp (°C): **1.8**
- Total Precip (mm): **0.0**
- Avg Wind (km/h): **5.02**
- Max Wind (km/h): **8.4**

## Charts (auto-updated)

![Average Temperature (30d)](reports/charts/avg_temp_30d.png)

![Daily Precipitation (30d)](reports/charts/precip_30d.png)

## Outputs

- `warehouse/city_conditions.duckdb`
- `reports/latest_kpis.csv`
- `reports/charts/*.png`
