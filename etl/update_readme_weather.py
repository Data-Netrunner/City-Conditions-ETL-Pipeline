import math
import pandas as pd

def _fmt(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return 'NA'
        return str(round(float(x), 2))
    except Exception:
        return 'NA'

def update_readme(readme_path, kpis_csv_path):
    df = pd.read_csv(kpis_csv_path)
    latest = df.iloc[0].to_dict() if not df.empty else {}
    lines = []
    lines.append('# City Conditions ETL (Daily)\n\n')
    lines.append('Automated end-to-end ETL pipeline that pulls daily-updating **weather + air quality** data, loads it into a DuckDB analytics warehouse, and publishes KPI reports + charts.\n\n')
    lines.append('## Data Sources\n\n')
    lines.append('Data is pulled from [Open-Meteo](https://open-meteo.com/) - a free, open-source weather and air quality API requiring no API key.\n\n')
    lines.append('| Source | API | Data Collected |\n')
    lines.append('|---|---|---|\n')
    lines.append('| Weather | [Open-Meteo Forecast API](https://api.open-meteo.com/v1/forecast) | Temperature, Precipitation, Wind Speed |\n')
    lines.append('| Air Quality | [Open-Meteo Air Quality API](https://air-quality-api.open-meteo.com/v1/air-quality) | PM2.5, PM10, NO2, Ozone |\n\n')
    if latest:
        lines.append('## Latest KPI Snapshot\n\n')
        lines.append(f"- Date: **{latest.get('day')}**\n")
        lines.append(f"- Avg Temp (C): **{_fmt(latest.get('avg_temp_c'))}**\n")
        lines.append(f"- Max Temp (C): **{_fmt(latest.get('max_temp_c'))}**\n")
        lines.append(f"- Total Precip (mm): **{_fmt(latest.get('total_precip_mm'))}**\n")
        lines.append(f"- Avg Wind (km/h): **{_fmt(latest.get('avg_windspeed_kmh'))}**\n")
        lines.append(f"- Max Wind (km/h): **{_fmt(latest.get('max_windspeed_kmh'))}**\n")
        if 'pm25_avg' in latest:
            lines.append(f"- PM2.5 Avg: **{_fmt(latest.get('pm25_avg'))}**\n")
            lines.append(f"- PM2.5 Peak: **{_fmt(latest.get('pm25_peak'))}**\n")
        lines.append('\n')
    lines.append('## Charts (auto-updated)\n\n')
    lines.append('![Average Temperature (30d)](reports/charts/avg_temp_30d.png)\n\n')
    lines.append('![Daily Precipitation (30d)](reports/charts/precip_30d.png)\n\n')
    lines.append('![PM2.5 Average (30d)](reports/charts/pm25_avg_30d.png)\n\n')
    lines.append('## Outputs\n\n')
    lines.append('- `warehouse/city_conditions.duckdb`\n')
    lines.append('- `reports/latest_kpis.csv`\n')
    lines.append('- `reports/run_log.csv`\n')
    lines.append('- `reports/charts/*.png`\n\n')
    lines.append('*Built by Andre Felix - Data updated daily via GitHub Actions*\n')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
