"""
History-store upsert semantics and the data-quality gate.

The history file is the only durable copy of the observation record — the
warehouse holds just Open-Meteo's rolling window. If an upsert ever dropped
older days, the training set would silently shrink.
"""

import os

import pandas as pd
import pytest

from etl import history_store
from etl.data_quality import assert_not_empty, assert_required_columns


# ---------------------------------------------------------------------------
# History store
# ---------------------------------------------------------------------------
@pytest.fixture
def temp_history(tmp_path, monkeypatch):
    """Point HISTORY_CSV at a throwaway file so tests never touch the repo."""
    path = tmp_path / "history" / "daily_observations.csv"
    monkeypatch.setattr(history_store, "HISTORY_CSV", str(path))
    return str(path)


def _write_history(path, days, temps):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pd.DataFrame({
        "day": days,
        "location_id": 1,
        "avg_temp_c": temps,
        "max_temp_c": [t + 4 for t in temps],
        "total_precip_mm": [0.0] * len(days),
        "avg_windspeed_kmh": [10.0] * len(days),
        "hours_observed": [24] * len(days),
    }).to_csv(path, index=False)


def test_load_returns_empty_when_no_history_yet(temp_history):
    out = history_store.load_daily_history(1)
    assert out.empty


def test_load_round_trips_and_parses_dates(temp_history):
    _write_history(temp_history, ["2026-03-01", "2026-03-02"], [5.0, 6.0])

    out = history_store.load_daily_history(1)

    assert len(out) == 2
    assert pd.api.types.is_datetime64_any_dtype(out["day"])
    assert out["day"].is_monotonic_increasing


def test_load_filters_by_location(temp_history):
    os.makedirs(os.path.dirname(temp_history), exist_ok=True)
    pd.DataFrame({
        "day": ["2026-03-01", "2026-03-01"],
        "location_id": [1, 2],
        "avg_temp_c": [5.0, 25.0],
        "max_temp_c": [9.0, 30.0],
        "total_precip_mm": [0.0, 0.0],
        "avg_windspeed_kmh": [10.0, 10.0],
        "hours_observed": [24, 24],
    }).to_csv(temp_history, index=False)

    out = history_store.load_daily_history(1)

    assert len(out) == 1
    assert out["avg_temp_c"].iloc[0] == 5.0


def test_history_columns_are_stable(temp_history):
    """Downstream feature code depends on these names."""
    _write_history(temp_history, ["2026-03-01"], [5.0])

    out = history_store.load_daily_history(1)

    for col in ["day", "avg_temp_c", "total_precip_mm", "avg_windspeed_kmh"]:
        assert col in out.columns


# ---------------------------------------------------------------------------
# Data quality gate
# ---------------------------------------------------------------------------
def test_missing_columns_raise():
    df = pd.DataFrame({"ts": [1], "temperature_c": [2.0]})

    with pytest.raises(ValueError, match="missing required columns"):
        assert_required_columns(df, ["ts", "temperature_c", "windspeed_kmh"], "weather")


def test_present_columns_pass():
    df = pd.DataFrame({"ts": [1], "temperature_c": [2.0]})

    assert_required_columns(df, ["ts", "temperature_c"], "weather")  # must not raise


def test_empty_frame_raises():
    with pytest.raises(ValueError, match="empty"):
        assert_not_empty(pd.DataFrame(), "weather_clean")


def test_none_frame_raises():
    with pytest.raises(ValueError):
        assert_not_empty(None, "weather_clean")


def test_populated_frame_passes():
    assert_not_empty(pd.DataFrame({"a": [1]}), "weather_clean")  # must not raise
