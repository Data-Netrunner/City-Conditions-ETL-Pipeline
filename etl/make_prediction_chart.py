"""Charts for the prediction section: predicted vs actual, and error over time."""

import os

import matplotlib
matplotlib.use("Agg")  # Required for headless environments (GitHub Actions has no display)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

BACKTEST_CSV = "reports/prediction_backtest.csv"


def _style_time_axis() -> None:
    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    plt.xticks(rotation=45, ha="right")
    ax.grid(True, which="major", axis="both", linestyle="--", linewidth=0.5)


def make_prediction_charts(charts_dir: str = "reports/charts", last_n: int = 30) -> None:
    """
    Two charts:
      1. predicted vs actual vs persistence baseline — does the line track?
      2. absolute error per day, model vs baseline — where does it go wrong?
    """
    if not os.path.exists(BACKTEST_CSV):
        print("No backtest file yet — prediction charts skipped.")
        return

    os.makedirs(charts_dir, exist_ok=True)

    df = pd.read_csv(BACKTEST_CSV)
    if df.empty:
        print("Backtest file is empty — prediction charts skipped.")
        return

    df["target_day"] = pd.to_datetime(df["target_day"])
    df = df.sort_values("target_day").tail(last_n)

    # --- 1) Predicted vs actual ------------------------------------------
    plt.figure()
    plt.plot(df["target_day"], df["actual_temp_c"],
             label="Actual", linewidth=2)
    plt.plot(df["target_day"], df["predicted_temp_c"],
             label="Model forecast", linestyle="--", marker="o", markersize=3)
    plt.plot(df["target_day"], df["baseline_temp_c"],
             label="Persistence baseline", linestyle=":", alpha=0.7)
    plt.title(f"Next-Day Temperature Forecast vs Actual (Last {len(df)} Scored Days)")
    plt.xlabel("Date")
    plt.ylabel("Average Temperature (°C)")
    _style_time_axis()
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, "forecast_vs_actual_30d.png"))
    plt.close()

    # --- 2) Absolute error per day ---------------------------------------
    plt.figure()
    plt.plot(df["target_day"], df["model_abs_err"],
             label="Model abs error", marker="o", markersize=3)
    plt.plot(df["target_day"], df["baseline_abs_err"],
             label="Baseline abs error", linestyle=":", alpha=0.8)
    plt.axhline(df["model_abs_err"].mean(), linestyle="--", linewidth=1,
                label=f"Model MAE = {df['model_abs_err'].mean():.2f} °C")
    plt.title("Forecast Absolute Error per Day")
    plt.xlabel("Date")
    plt.ylabel("Absolute error (°C)")
    _style_time_axis()
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(os.path.join(charts_dir, "forecast_error_30d.png"))
    plt.close()

    print("Prediction charts written.")
