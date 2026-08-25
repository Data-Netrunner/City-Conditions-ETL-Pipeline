"""Shared pytest fixtures and path setup."""

import os
import sys

import pandas as pd
import pytest

# Make `import etl.*` work when pytest is run from the repo root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.fixture
def contiguous_daily():
    """
    40 consecutive days of plausible daily weather, no gaps.

    Temperatures follow a gentle warming trend with a little wobble, so lag
    and rolling features have something real to latch onto.
    """
    days = pd.date_range("2026-03-01", periods=40, freq="D")
    return pd.DataFrame({
        "day": days,
        "location_id": 1,
        "avg_temp_c": [5.0 + 0.25 * i + (1.5 if i % 3 == 0 else -1.0)
                       for i in range(40)],
        "max_temp_c": [9.0 + 0.25 * i for i in range(40)],
        "total_precip_mm": [0.0 if i % 4 else 3.2 for i in range(40)],
        "avg_windspeed_kmh": [10.0 + (i % 5) for i in range(40)],
        "hours_observed": 24,
    })


@pytest.fixture
def gapped_daily():
    """
    Two separate blocks of days with a four-month hole between them —
    the exact shape of the real warehouse history.
    """
    block_a = pd.date_range("2026-02-01", periods=10, freq="D")
    block_b = pd.date_range("2026-06-01", periods=10, freq="D")
    days = block_a.append(block_b)

    return pd.DataFrame({
        "day": days,
        "location_id": 1,
        # Block A is winter-cold, block B is summer-warm. If a lag feature
        # ever bridges the gap, the resulting row is nonsense and easy to spot.
        "avg_temp_c": [-8.0] * 10 + [20.0] * 10,
        "max_temp_c": [-3.0] * 10 + [25.0] * 10,
        "total_precip_mm": [0.0] * 20,
        "avg_windspeed_kmh": [12.0] * 20,
        "hours_observed": 24,
    })
