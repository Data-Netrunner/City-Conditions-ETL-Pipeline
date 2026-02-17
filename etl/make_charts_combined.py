import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def _style_time_axis():
    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    plt.xticks(rotation=45, ha="right")
    ax.grid(True, which="major", axis="both", linestyle="--", linewidth=0.5)

def make_charts(kpis_csv: str, charts_dir: str = "reports/charts") -> None:
    os.makedirs(charts_dir, exist_ok=True)

    df = pd.read_csv(kpis_csv)
    if df.empty:
        return

    df["day"] = pd.to_datetime(df["day"])
    df = df.sort_values("day")

    # 1) Avg Temp (30d)
    plt.figure()
    plt.plot(df["day"], df["avg_temp_c"], label="Avg Temp")
    plt.title("Average Temperature (Last 30 Days)")
    plt.xlabel("Date")
    plt.ylabel("Temperature (°C)")
    _style_time_axis()
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, "avg_temp_30d.png"))
    plt.close()

    # 2) Total Precip (30d)
    plt.figure()
    plt.plot(df["day"], df["total_precip_mm"], label="Total Precip")
    plt.title("Total Precipitation per Day (Last 30 Days)")
    plt.xlabel("Date")
    plt.ylabel("Precipitation (mm)")
    _style_time_axis()
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, "precip_30d.png"))
    plt.close()

    # 3) PM2.5 Avg (30d)
    if "pm25_avg" in df.columns:
        plt.figure()
        plt.plot(df["day"], df["pm25_avg"], label="PM2.5 Avg")
        plt.title("PM2.5 Average (Last 30 Days)")
        plt.xlabel("Date")
        plt.ylabel("PM2.5 (µg/m³)")
        _style_time_axis()
        plt.legend(loc="best")
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, "pm25_avg_30d.png"))
        plt.close()
