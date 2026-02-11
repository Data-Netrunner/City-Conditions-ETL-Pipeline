import pandas as pd

def update_readme(readme_path: str, kpis_csv_path: str) -> None:
    df = pd.read_csv(kpis_csv_path)

    latest = df.iloc[0].to_dict() if not df.empty else {}

    lines = []
    lines.append("# City Conditions ETL (Daily)\n\n")
    lines.append("This project builds an end-to-end ETL pipeline that pulls daily-updating weather data, cleans it, loads it into a DuckDB analytics warehouse, and publishes stakeholder-ready KPIs and charts.\n\n")

    if latest:
        lines.append("## Latest KPI snapshot\n\n")
        lines.append(f"- Date: **{latest.get('day')}**\n")
        lines.append(f"- Avg Temp (°C): **{round(float(latest.get('avg_temp_c', 0)), 2)}**\n")
        lines.append(f"- Max Temp (°C): **{round(float(latest.get('max_temp_c', 0)), 2)}**\n")
        lines.append(f"- Total Precip (mm): **{round(float(latest.get('total_precip_mm', 0)), 2)}**\n")
        lines.append(f"- Avg Wind (km/h): **{round(float(latest.get('avg_windspeed_kmh', 0)), 2)}**\n")
        lines.append(f"- Max Wind (km/h): **{round(float(latest.get('max_windspeed_kmh', 0)), 2)}**\n\n")

    lines.append("## Charts (auto-updated)\n\n")
    lines.append("![Average Temperature (30d)](reports/charts/avg_temp_30d.png)\n\n")
    lines.append("![Daily Precipitation (30d)](reports/charts/precip_30d.png)\n\n")

    lines.append("## Outputs\n\n")
    lines.append("- `warehouse/city_conditions.duckdb`\n")
    lines.append("- `reports/latest_kpis.csv`\n")
    lines.append("- `reports/charts/*.png`\n")

    with open(readme_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
