"""Transform-layer invariants: bad data must not reach the warehouse."""

import pandas as pd

from etl.transform_weather import clean_weather
from etl.transform_air_quality import clean_air_quality


def test_impossible_temperatures_are_nulled():
    """A sensor spike of 999 C must not survive into the warehouse."""
    df = pd.DataFrame({
        "ts": pd.to_datetime(["2026-03-01 00:00", "2026-03-01 01:00",
                              "2026-03-01 02:00"]),
        "temperature_c":    [5.0, 999.0, -80.0],
        "precipitation_mm": [0.0, 0.0, 0.0],
        "windspeed_kmh":    [10.0, 10.0, 10.0],
    })

    out = clean_weather(df)

    assert out["temperature_c"].iloc[0] == 5.0
    assert pd.isna(out["temperature_c"].iloc[1]), "999 C should be nulled"
    assert pd.isna(out["temperature_c"].iloc[2]), "-80 C should be nulled"


def test_negative_precipitation_and_wind_are_nulled():
    """Negative rainfall is physically impossible."""
    df = pd.DataFrame({
        "ts": pd.to_datetime(["2026-03-01 00:00", "2026-03-01 01:00"]),
        "temperature_c":    [5.0, 5.0],
        "precipitation_mm": [-3.0, 1.0],
        "windspeed_kmh":    [-1.0, 8.0],
    })

    out = clean_weather(df)

    assert pd.isna(out["precipitation_mm"].iloc[0])
    assert pd.isna(out["windspeed_kmh"].iloc[0])
    assert out["precipitation_mm"].iloc[1] == 1.0


def test_duplicate_timestamps_are_dropped_and_rows_sorted():
    """Upserts key on ts, so duplicates must be resolved before loading."""
    df = pd.DataFrame({
        "ts": pd.to_datetime(["2026-03-01 02:00", "2026-03-01 00:00",
                              "2026-03-01 02:00"]),
        "temperature_c":    [7.0, 5.0, 7.0],
        "precipitation_mm": [0.0, 0.0, 0.0],
        "windspeed_kmh":    [10.0, 10.0, 10.0],
    })

    out = clean_weather(df)

    assert len(out) == 2, "duplicate timestamp should be dropped"
    assert out["ts"].is_monotonic_increasing, "rows must come out sorted"


def test_unparseable_timestamps_are_dropped():
    df = pd.DataFrame({
        "ts": ["2026-03-01 00:00", "not-a-date"],
        "temperature_c":    [5.0, 6.0],
        "precipitation_mm": [0.0, 0.0],
        "windspeed_kmh":    [10.0, 10.0],
    })

    out = clean_weather(df)

    assert len(out) == 1


def test_negative_pollutant_readings_are_nulled():
    """Concentrations cannot be below zero."""
    df = pd.DataFrame({
        "ts": pd.to_datetime(["2026-03-01 00:00", "2026-03-01 01:00"]),
        "pm25": [-5.0, 8.0],
        "pm10": [-2.0, 9.0],
        "no2":  [10.0, 11.0],
        "o3":   [40.0, 42.0],
    })

    out = clean_air_quality(df)

    assert pd.isna(out["pm25"].iloc[0])
    assert pd.isna(out["pm10"].iloc[0])
    assert out["pm25"].iloc[1] == 8.0
