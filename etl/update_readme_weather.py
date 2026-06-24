import math
import pandas as pd

def _fmt(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return "NA"
        return str(round(float(x), 2))
    except Exception:
        return "NA"

def update_readme(readme_path, kpis_csv_path):
    df = pd.read_csv(kpis_csv_path)
    latest = df.iloc[0].to_dict() if not df.empty else {}
    lines = []
    lines.append("# City Conditions ETL (Daily)\n\n")
    lines.append("Data from [Open-Meteo](https://open-meteo.com/)\n\n")
    if latest:
        lines.append("## Latest KPI Snapshot\n\n")
        lines.append(f"- Date: **{latest.get('day')}**\n")
        lines.append(f"- Avg Temp (C): **{_fmt(latest.get('avg_temp_c'))}**\n")
        lines.append(f"- PM2.5 Avg: **{_fmt(latest.get('pm25_avg'))}**\n")
    lines.append("\n## Charts\n\n")
    lines.append("![Temp](reports/charts/avg_temp_30d.png)\n\n")
    lines.append("![Precip](reports/charts/precip_30d.png)\n\n")
    lines.append("![PM2.5](reports/charts/pm25_avg_30d.png)\n\n")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
