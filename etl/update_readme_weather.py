import pandas as pd
import math

def _fmt(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return "NA"
        return str(round(float(x), 2))
    except Exception:
        return "NA"

def update_readme(readme_path: str, kpis_csv_path: str) -> None:
    df = pd.read_csv(kpis_csv_path)
    latest = df.iloc[0].to_dict() if not df.empty else {}

    lines = []
    lines.append("# City Conditions ETL (Daily)\n\n")
    lines.append("Automated end-to-end ETL pipeline that pulls daily-updating **weather + air quality** data, loads it into a DuckDB analytics warehouse, and publishes stakeholder-ready KPIs + charts.\n\n")

    if latest:
        lines.append("## Latest KPI snapshot\n\n")
        lines.append(f"- Date: **{latest.get('day')}**\n")
        lines.append(f"- Avg Temp (°C): **{_fmt(latest.get('avg_temp_c'))}**\n")
        lines.append(f"- Max Temp (°C): **{_fmt(latest.get('max_temp_c'))}**\n")
        lines.append(f"- Total Precip (mm): **{_fmt(latest.get('total_precip_mm'))}**\n")
        lines.append(f"- Avg Wind (km/h): **{_fmt(latest.get('avg_windspeed_kmh'))}**\n")
        lines.append(f"- Max Wind (km/h): **{_fmt(latest.get('max_windspeed_kmh'))}**\n")
        # AQ (may be NA if missing)
        if "pm25_avg" in latest:
            lines.append(f"- PM2.5 Avg: **{_fmt(latest.get('pm25_avg'))}**\n")
            lines.append(f"- PM2.5 Peak: **{_fmt(latest.get('pm25_peak'))}**\n")
        lines.append("\n")

    lines.append("## Charts (auto-updated)\n\n")
    lines.append("![Average Temperature (30d)](reports/charts/avg_temp_30d.png)\n\n")
    lines.append("![Daily Precipitation (30d)](reports/charts/precip_30d.png)\n\n")
    lines.append("![PM2.5 Average (30d)](reports/charts/pm25_avg_30d.png)\n\n")

    lines.append("## Outputs\n\n")
    lines.append("- `warehouse/city_conditions.duckdb`\n")
    lines.append("- `reports/latest_kpis.csv`\n")
    lines.append("- `reports/charts/*.png`\n")

    with open(readme_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
