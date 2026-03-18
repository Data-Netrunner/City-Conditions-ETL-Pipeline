import os
from datetime import datetime
import pandas as pd

LOG_PATH = "reports/run_log.csv"

def assert_required_columns(df: pd.DataFrame, required: list[str], df_name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{df_name} missing required columns: {missing}")

def assert_not_empty(df: pd.DataFrame, df_name: str) -> None:
    if df is None or df.empty:
        raise ValueError(f"{df_name} is empty")

def append_run_log(
    weather_rows: int,
    aq_rows: int,
    kpi_rows: int,
    status: str,
    message: str = ""
) -> None:
    os.makedirs("reports", exist_ok=True)

    row = pd.DataFrame([{
        "run_ts_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "weather_rows": weather_rows,
        "aq_rows": aq_rows,
        "kpi_rows": kpi_rows,
        "status": status,
        "message": message
    }])

    if os.path.exists(LOG_PATH):
        existing = pd.read_csv(LOG_PATH)
        out = pd.concat([existing, row], ignore_index=True)
    else:
        out = row

    out.to_csv(LOG_PATH, index=False)
