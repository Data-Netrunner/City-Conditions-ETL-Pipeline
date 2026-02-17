import os
import pandas as pd
import matplotlib.pyplot as plt

def make_charts(kpis_csv: str, charts_dir: str = "reports/charts") -> None:
    os.makedirs(charts_dir, exist_ok=True)

    df = pd.read_csv(kpis_csv)
    if df.empty:
        return

    df["day"] = pd.to_datetime(df["day"])
    df = df.sort_values("day")

    # 1) Avg Temp (30d)
    plt.figure()
    plt.plot(df["day"], df["avg_temp_c"])
    plt.xticks(rotation=45, ha="right")
    plt.title("Average Temperature (Last 30 Days)")
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, "avg_temp_30d.png"))
    plt.close()

    # 2) Total Precip (30d)
    plt.figure()
    plt.plot(df["day"], df["total_precip_mm"])
    plt.xticks(rotation=45, ha="right")
    plt.title("Total Precipitation per Day (Last 30 Days)")
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, "precip_30d.png"))
    plt.close()

    # 3) PM2.5 Avg (30d) - only if column exists
    if "pm25_avg" in df.columns:
        plt.figure()
        plt.plot(df["day"], df["pm25_avg"])
        plt.xticks(rotation=45, ha="right")
        plt.title("PM2.5 Average (Last 30 Days)")
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, "pm25_avg_30d.png"))
        plt.close()
