"""
Regression tests for the two extrapolation guards.

Both of these exist because of a real defect: on 2026-08-25 the pipeline
published a next-day forecast of 40.07 C for Toronto in August. The cause was
seasonal day-of-year features fitted on 21 rows covering only February and
June, then asked to extrapolate into late August.
"""

import pandas as pd
import pytest

from etl.predict_temperature import (
    BASE_FEATURES,
    MAX_DAILY_SWING_C,
    SEASONAL_FEATURES,
    apply_sanity_bounds,
    build_features,
    select_features,
    training_table,
)


def _train_from(daily):
    return training_table(build_features(daily))


# ---------------------------------------------------------------------------
# Guard 1 — seasonal features are gated on real annual coverage
# ---------------------------------------------------------------------------
def test_seasonal_features_off_with_short_history(contiguous_daily):
    """40 days spanning 40 days is nowhere near a year."""
    cols = select_features(_train_from(contiguous_daily))

    assert cols == BASE_FEATURES
    assert "doy_sin" not in cols


def test_seasonal_features_off_with_gappy_partial_year(gapped_daily):
    """
    The exact failure case: February plus June, wide span, very few rows.
    Span alone must not be enough to unlock the seasonal features.
    """
    cols = select_features(_train_from(gapped_daily))

    assert "doy_sin" not in cols, "sparse coverage must not enable seasonality"


def test_seasonal_features_on_with_a_full_year():
    """Once there is a genuine year of daily history, seasonality is allowed."""
    days = pd.date_range("2025-01-01", periods=420, freq="D")
    daily = pd.DataFrame({
        "day": days,
        "location_id": 1,
        "avg_temp_c": [10.0 + 15.0 * pd.Timestamp(d).dayofyear / 365.0
                       for d in days],
        "max_temp_c": [15.0] * len(days),
        "total_precip_mm": [0.0] * len(days),
        "avg_windspeed_kmh": [10.0] * len(days),
        "hours_observed": 24,
    })

    cols = select_features(_train_from(daily))

    assert "doy_sin" in cols and "doy_cos" in cols
    assert cols == BASE_FEATURES + SEASONAL_FEATURES


# ---------------------------------------------------------------------------
# Guard 2 — physical sanity bounds on the published prediction
# ---------------------------------------------------------------------------
def test_the_40_degree_bug_is_clamped(contiguous_daily):
    """The literal regression test: 40 C must never be published again."""
    train = _train_from(contiguous_daily)
    baseline = 17.44

    bounded, was_clamped = apply_sanity_bounds(40.07, baseline, train)

    assert was_clamped is True
    assert bounded < 40.07
    assert bounded <= baseline + MAX_DAILY_SWING_C


def test_absurd_cold_is_clamped(contiguous_daily):
    train = _train_from(contiguous_daily)
    baseline = 17.44

    bounded, was_clamped = apply_sanity_bounds(-30.0, baseline, train)

    assert was_clamped is True
    assert bounded >= baseline - MAX_DAILY_SWING_C


def test_plausible_prediction_passes_through_untouched(contiguous_daily):
    """A sane forecast must not be altered — the guard is a backstop, not a filter."""
    train = _train_from(contiguous_daily)

    bounded, was_clamped = apply_sanity_bounds(18.67, 17.44, train)

    assert was_clamped is False
    assert bounded == pytest.approx(18.67)


def test_clamp_never_moves_more_than_the_swing_limit(contiguous_daily):
    """Whatever the model emits, the result stays within the swing band."""
    train = _train_from(contiguous_daily)
    baseline = 12.0

    for raw in (-500.0, -20.0, 0.0, 12.0, 25.0, 500.0):
        bounded, _ = apply_sanity_bounds(raw, baseline, train)
        assert baseline - MAX_DAILY_SWING_C <= bounded <= baseline + MAX_DAILY_SWING_C
