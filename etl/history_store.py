"""
Durable daily history.

WHY THIS FILE EXISTS
--------------------
The pipeline only ever pulls a rolling ~7-day window from Open-Meteo, and the
DuckDB warehouse was never committed back by the GitHub Action. That means the
warehouse silently reset to whatever was last checked in — so no matter how
many days the pipeline ran, it never accumulated more than a couple of weeks
of history. A forecasting model trained on that is training on nothing.

The fix is an append-only CSV of *observed* daily aggregates that IS committed
on every run. It is small, diffs cleanly in git (unlike a binary .duckdb), and
makes the warehouse a rebuildable derived artifact rather than the only copy
of the data.
"""

import os

import pandas as pd
import duckdb

HISTORY_CSV = "data/history/daily_observations.csv"

HISTORY_COLS = [
    "day", "location_id", "avg_temp_c", "max_temp_c",
    "total_precip_mm", "avg_windspeed_kmh", "hours_observed",
]


def _daily_from_warehouse(db_path: str, location_id: int = 1) -> pd.DataFrame:
    """
    Roll hourly rows up to one row per day.

    Only days strictly before today are taken. Today is still partial, and
    anything after today is an Open-Meteo *forecast* — storing those as
    observations is what would leak the answer into a next-day model.
    """
    con = duckdb.connect(db_path, read_only=True)
    df = con.execute(
        """
        SELECT
            DATE(ts)              AS day,
            location_id,
            AVG(temperature_c)    AS avg_temp_c,
            MAX(temperature_c)    AS max_temp_c,
            SUM(precipitation_mm) AS total_precip_mm,
            AVG(windspeed_kmh)    AS avg_windspeed_kmh,
            COUNT(*)              AS hours_observed
        FROM fact_weather_hourly
        WHERE location_id = ?
          AND DATE(ts) < CURRENT_DATE
        GROUP BY 1, 2
        ORDER BY 1
        """,
        [location_id],
    ).df()
    con.close()

    df["day"] = pd.to_datetime(df["day"]).dt.date.astype(str)

    # A day with only a few hours recorded would skew its own daily average.
    return df[df["hours_observed"] >= 20].reset_index(drop=True)


def append_daily_history(db_path: str, location_id: int = 1) -> pd.DataFrame:
    """
    Merge today's warehouse view into the committed history file.

    Upsert semantics on (day, location_id): a day already in the file gets
    refreshed (Open-Meteo revises recent observations), new days get added,
    and days that have aged out of the API's rolling window are preserved.
    """
    os.makedirs(os.path.dirname(HISTORY_CSV), exist_ok=True)

    fresh = _daily_from_warehouse(db_path, location_id)

    if os.path.exists(HISTORY_CSV):
        prior = pd.read_csv(HISTORY_CSV)
        prior["day"] = prior["day"].astype(str)
        merged = pd.concat([prior, fresh], ignore_index=True)
        # keep="last" -> the freshly pulled version of a day wins
        merged = merged.drop_duplicates(subset=["day", "location_id"], keep="last")
    else:
        merged = fresh

    merged = merged[HISTORY_COLS].sort_values("day").reset_index(drop=True)
    merged.to_csv(HISTORY_CSV, index=False)

    print(f"Daily history: {len(merged)} observed days on file "
          f"({merged['day'].min()} to {merged['day'].max()}).")
    return merged


def load_daily_history(location_id: int = 1) -> pd.DataFrame:
    """Read the accumulated history back for modelling."""
    if not os.path.exists(HISTORY_CSV):
        return pd.DataFrame(columns=HISTORY_COLS)

    df = pd.read_csv(HISTORY_CSV)
    df = df[df["location_id"] == location_id].copy()
    df["day"] = pd.to_datetime(df["day"])
    return df.sort_values("day").reset_index(drop=True)
