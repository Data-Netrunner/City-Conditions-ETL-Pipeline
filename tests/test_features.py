"""
Feature-engineering invariants.

The critical property here is NO LEAKAGE ACROSS CALENDAR GAPS. The real history
has a four-month hole in it; a lag feature that silently bridges that hole would
pair a February day with a June day and quietly poison the model.
"""

import pandas as pd

from etl.predict_temperature import (
    BASE_FEATURES,
    FEATURE_COLS,
    build_features,
    training_table,
)


def test_target_is_the_following_day(contiguous_daily):
    """target_temp_c on row d must equal avg_temp_c on row d+1."""
    feat = build_features(contiguous_daily)

    for i in range(len(feat) - 1):
        assert feat["target_temp_c"].iloc[i] == feat["avg_temp_c"].iloc[i + 1]
        assert feat["target_day"].iloc[i] == feat["day"].iloc[i] + pd.Timedelta(days=1)


def test_lag_features_use_only_past_and_present(contiguous_daily):
    """temp_lag1 is today, temp_lag2 is yesterday — never tomorrow."""
    feat = build_features(contiguous_daily)

    assert feat["temp_lag1"].iloc[5] == feat["avg_temp_c"].iloc[5]
    assert feat["temp_lag2"].iloc[5] == feat["avg_temp_c"].iloc[4]
    assert feat["temp_lag3"].iloc[5] == feat["avg_temp_c"].iloc[3]


def test_no_training_row_bridges_a_calendar_gap(gapped_daily):
    """
    The regression test that matters most.

    With a Feb block and a June block, no usable training row may pair a
    February feature with a June target. Every surviving row must sit inside
    one contiguous block.
    """
    train = training_table(build_features(gapped_daily))

    for _, row in train.iterrows():
        # target_day must be exactly one day after day — never a 100-day jump
        assert row["target_day"] - row["day"] == pd.Timedelta(days=1)
        # and the temperature must not teleport between seasons
        assert abs(row["target_temp_c"] - row["temp_lag1"]) < 10.0, (
            f"row on {row['day'].date()} bridges the gap: "
            f"temp_lag1={row['temp_lag1']} target={row['target_temp_c']}"
        )


def test_gap_reduces_usable_rows(gapped_daily, contiguous_daily):
    """20 gapped days must yield fewer training rows than 20 contiguous ones."""
    gapped_rows = len(training_table(build_features(gapped_daily)))
    contiguous_rows = len(training_table(build_features(contiguous_daily.head(20))))

    assert gapped_rows < contiguous_rows


def test_training_table_has_no_missing_values(contiguous_daily):
    """Anything with a NaN feature or target must be dropped before fitting."""
    train = training_table(build_features(contiguous_daily))

    assert not train[FEATURE_COLS + ["target_temp_c"]].isna().any().any()
    assert len(train) > 0


def test_rolling_window_needs_a_full_window(contiguous_daily):
    """temp_roll7 must be NaN until seven days are available."""
    feat = build_features(contiguous_daily)

    assert pd.isna(feat["temp_roll7"].iloc[5]), "day 6 cannot have a 7-day mean"
    assert not pd.isna(feat["temp_roll7"].iloc[6]), "day 7 should have one"


def test_seasonal_columns_exist_but_are_not_in_base_features():
    """The seasonal pair is built every run but only used when it's earned."""
    assert "doy_sin" in FEATURE_COLS
    assert "doy_sin" not in BASE_FEATURES
