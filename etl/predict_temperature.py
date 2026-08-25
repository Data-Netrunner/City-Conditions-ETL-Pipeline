"""
Next-day average temperature forecasting.

Design notes (these are the interview talking points):

1. OBSERVED DATA ONLY. Open-Meteo's forecast endpoint returns past days AND
   future days in the same payload. Training a "next-day" model on rows that
   are themselves Open-Meteo forecasts is target leakage: the model would just
   learn to copy the API. Everything here reads the observed-only history file.

2. RIDGE, NOT A FOREST. At n~50 daily rows a tree ensemble overfits, and trees
   cannot extrapolate at all. A regularised linear model is the honest choice
   at this sample size.

3. BASELINE OR IT DIDN'T HAPPEN. Every metric is reported next to persistence
   ("tomorrow = today"), a surprisingly strong weather baseline. A model that
   cannot beat persistence has no value, and saying so is the point.

4. WALK-FORWARD VALIDATION. A random train/test split on a time series leaks
   the future into the past. Scoring is expanding-window: to score day i, fit
   only on days < i.

5. TWO GUARDS AGAINST EXTRAPOLATION. Ridge's ability to extrapolate is a
   double-edged sword. Trained on 21 days spanning February and June and then
   asked about late August, the seasonal day-of-year features extrapolated to
   a 40 C forecast for Toronto. So:

     (a) The doy_sin/doy_cos seasonal pair is only used once the history
         actually covers most of a year. Below that the seasonal cycle is not
         identifiable and those features do more harm than good.

     (b) Every prediction is bounded by a physical sanity check before it is
         published, and any clamping is recorded rather than hidden.

   Both guards apply inside the backtest too, so the reported accuracy is the
   accuracy of what actually ships.
"""

import os
from datetime import date

import numpy as np
import pandas as pd

from etl.history_store import load_daily_history

from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

PREDICTIONS_CSV = "reports/predictions.csv"
METRICS_CSV     = "reports/prediction_metrics.csv"
BACKTEST_CSV    = "reports/prediction_backtest.csv"

# Always-available features, derived from days <= d to predict day d + 1.
BASE_FEATURES = [
    "temp_lag1", "temp_lag2", "temp_lag3",
    "temp_roll3", "temp_roll7",
    "temp_delta1",
    "precip_lag1", "wind_lag1",
]

# Seasonality. Only switched on once the history can actually support it.
SEASONAL_FEATURES = ["doy_sin", "doy_cos"]

# Everything build_features() produces — used for assembling the launch row.
FEATURE_COLS = BASE_FEATURES + SEASONAL_FEATURES

MIN_TRAIN_ROWS = 15    # below this there is not enough history to fit anything

# Seasonal features need real coverage of the annual cycle before they mean
# anything. Roughly: a year's worth of rows spanning most of a year.
SEASONAL_MIN_ROWS      = 120
SEASONAL_MIN_SPAN_DAYS = 300

# Toronto's largest day-over-day change in daily MEAN temperature sits well
# inside this. Anything beyond it is a model failure, not weather.
MAX_DAILY_SWING_C = 12.0


# ----------------------------------------------------------------------------
# 1. Load observed daily history
# ----------------------------------------------------------------------------
def load_daily_observed(location_id: int = 1) -> pd.DataFrame:
    """
    Read the accumulated daily observation history.

    Deliberately reads the committed history file rather than the warehouse:
    the warehouse only ever holds Open-Meteo's rolling window, so querying it
    directly caps the model at ~2 weeks of training data no matter how long
    the pipeline has been running.
    """
    return load_daily_history(location_id)


# ----------------------------------------------------------------------------
# 2. Feature engineering
# ----------------------------------------------------------------------------
def build_features(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Turn the daily series into a supervised learning table.

    One row per day d, with features built only from information available on
    day d, and target = the observed average temperature on day d + 1.

    The history has calendar gaps. Reindexing onto a complete daily calendar
    first means lags spanning a gap come out as NaN and get dropped, rather
    than silently pairing February with June.
    """
    if daily.empty:
        return pd.DataFrame()

    full_range = pd.date_range(daily["day"].min(), daily["day"].max(), freq="D")
    d = daily.set_index("day").reindex(full_range)
    d.index.name = "day"

    # --- lagged temperature: what we knew as of day d ---
    d["temp_lag1"] = d["avg_temp_c"].shift(0)   # today's observed mean
    d["temp_lag2"] = d["avg_temp_c"].shift(1)
    d["temp_lag3"] = d["avg_temp_c"].shift(2)

    # --- smoothed levels: rolling means damp single-day noise ---
    d["temp_roll3"] = d["avg_temp_c"].rolling(3).mean()
    d["temp_roll7"] = d["avg_temp_c"].rolling(7).mean()

    # --- momentum: is it warming or cooling? ---
    d["temp_delta1"] = d["avg_temp_c"] - d["avg_temp_c"].shift(1)

    # --- other same-day conditions ---
    d["precip_lag1"] = d["total_precip_mm"]
    d["wind_lag1"]   = d["avg_windspeed_kmh"]

    # --- seasonality: day-of-year as a circle, so Dec 31 sits next to Jan 1 ---
    doy = d.index.dayofyear
    d["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    d["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)

    # --- target: tomorrow's observed average temperature ---
    d["target_temp_c"] = d["avg_temp_c"].shift(-1)
    d["target_day"]    = d.index + pd.Timedelta(days=1)

    return d.reset_index()


def training_table(feat: pd.DataFrame) -> pd.DataFrame:
    """Rows usable for fitting: every feature and the target must be present."""
    if feat.empty:
        return feat
    return feat.dropna(subset=FEATURE_COLS + ["target_temp_c"]).reset_index(drop=True)


def select_features(train_slice: pd.DataFrame) -> list:
    """
    Decide whether the seasonal pair has earned its place.

    With only a few weeks of gappy history, doy_sin/doy_cos are not seasonality
    — they are two arbitrary numbers that happen to separate the February rows
    from the June rows, and the model leans on them hard. Asked about a date
    outside that range, it extrapolates the sine wave into nonsense (this is
    exactly how a 40 C August forecast for Toronto got published).

    Computed from the slice the model is actually fitted on, so the backtest
    makes the same decision the production run would have made on that date.
    """
    if len(train_slice) < SEASONAL_MIN_ROWS:
        return list(BASE_FEATURES)

    span_days = (train_slice["day"].max() - train_slice["day"].min()).days
    if span_days < SEASONAL_MIN_SPAN_DAYS:
        return list(BASE_FEATURES)

    return list(BASE_FEATURES) + list(SEASONAL_FEATURES)


def apply_sanity_bounds(pred: float, baseline: float,
                        train_slice: pd.DataFrame):
    """
    Bound the prediction by physical plausibility before publishing it.

    Two constraints, whichever is tighter:
      - within MAX_DAILY_SWING_C of today's observed mean
      - within 5 C of the range of temperatures ever observed

    Returns (bounded_prediction, was_clamped). A clamp firing is a signal the
    model is unhealthy, so it gets recorded in predictions.csv rather than
    quietly swallowed.
    """
    lo = max(baseline - MAX_DAILY_SWING_C, train_slice["target_temp_c"].min() - 5.0)
    hi = min(baseline + MAX_DAILY_SWING_C, train_slice["target_temp_c"].max() + 5.0)

    if lo > hi:  # degenerate history — fall back to the swing bound alone
        lo, hi = baseline - MAX_DAILY_SWING_C, baseline + MAX_DAILY_SWING_C

    bounded = float(np.clip(pred, lo, hi))
    return bounded, bool(abs(bounded - pred) > 1e-9)


def _new_model():
    """
    RidgeCV picks its own regularisation strength by cross-validation, so there
    is no hand-tuned magic number. Scaling first matters: ridge penalises large
    coefficients, and the raw features are on wildly different scales.
    """
    return make_pipeline(
        StandardScaler(),
        RidgeCV(alphas=np.logspace(-3, 3, 25)),
    )


# ----------------------------------------------------------------------------
# 3. Walk-forward backtest
# ----------------------------------------------------------------------------
def backtest(train: pd.DataFrame, min_train: int = MIN_TRAIN_ROWS) -> pd.DataFrame:
    """
    Expanding-window validation. For each day i past the warm-up, fit on days
    0..i-1 only and predict day i.

    Feature selection and sanity bounds are applied per fold, so these numbers
    describe the system that actually ships — not an idealised version of it.
    """
    rows = []
    if len(train) <= min_train:
        return pd.DataFrame(rows)

    for i in range(min_train, len(train)):
        past = train.iloc[:i]
        cols = select_features(past)

        model = _new_model()
        model.fit(past[cols], past["target_temp_c"])

        raw      = float(model.predict(train.iloc[i:i + 1][cols])[0])
        baseline = float(train.loc[i, "temp_lag1"])
        pred, clamped = apply_sanity_bounds(raw, baseline, past)

        rows.append({
            "target_day":       train.loc[i, "target_day"],
            "actual_temp_c":    float(train.loc[i, "target_temp_c"]),
            "predicted_temp_c": pred,
            "raw_model_temp_c": raw,
            "clamped":          clamped,
            # Persistence baseline: "tomorrow will be like today".
            "baseline_temp_c":  baseline,
            "n_features":       len(cols),
        })

    out = pd.DataFrame(rows)
    out["model_abs_err"]    = (out["predicted_temp_c"] - out["actual_temp_c"]).abs()
    out["baseline_abs_err"] = (out["baseline_temp_c"]  - out["actual_temp_c"]).abs()
    return out


def summarise(bt: pd.DataFrame) -> dict:
    """MAE / RMSE for model and baseline, plus forecast skill score."""
    if bt.empty:
        return {}

    def _rmse(err):
        return float(np.sqrt((err ** 2).mean()))

    model_mae  = float(bt["model_abs_err"].mean())
    base_mae   = float(bt["baseline_abs_err"].mean())
    model_rmse = _rmse(bt["predicted_temp_c"] - bt["actual_temp_c"])
    base_rmse  = _rmse(bt["baseline_temp_c"]  - bt["actual_temp_c"])

    # Skill: the share of the baseline's error the model removes. Positive =
    # better than persistence, negative = worse. Published either way.
    skill = (base_mae - model_mae) / base_mae if base_mae > 0 else float("nan")

    return {
        "n_scored_days":        int(len(bt)),
        "model_mae_c":          round(model_mae, 3),
        "model_rmse_c":         round(model_rmse, 3),
        "baseline_mae_c":       round(base_mae, 3),
        "baseline_rmse_c":      round(base_rmse, 3),
        "skill_vs_persistence": round(skill, 3),
        "n_clamped":            int(bt["clamped"].sum()),
    }


# ----------------------------------------------------------------------------
# 4. Predict tomorrow + persist outputs
# ----------------------------------------------------------------------------
def predict_next_day(location_id: int = 1) -> dict:
    """
    Full prediction step. Returns a dict the README writer consumes.
    Degrades gracefully: too little history skips the forecast rather than
    crashing the pipeline.
    """
    os.makedirs("reports", exist_ok=True)

    daily = load_daily_observed(location_id)
    feat  = build_features(daily)
    train = training_table(feat)

    result = {
        "trained_rows":     int(len(train)),
        "target_day":       None,
        "predicted_temp_c": None,
        "baseline_temp_c":  None,
        "seasonal_used":    False,
        "n_features":       0,
        "clamped":          False,
        "metrics":          {},
    }

    if len(train) < MIN_TRAIN_ROWS:
        print(f"Only {len(train)} usable training rows "
              f"(need {MIN_TRAIN_ROWS}) — prediction skipped this run.")
        return result

    # --- backtest on everything we have, then report it ---
    bt      = backtest(train)
    metrics = summarise(bt)
    result["metrics"] = metrics

    if not bt.empty:
        bt_out = bt.copy()
        bt_out["target_day"] = pd.to_datetime(bt_out["target_day"]).dt.date
        bt_out.to_csv(BACKTEST_CSV, index=False)

    # --- fit on ALL history, then forecast the next day ---
    cols = select_features(train)
    result["seasonal_used"] = "doy_sin" in cols
    result["n_features"]    = len(cols)

    model = _new_model()
    model.fit(train[cols], train["target_temp_c"])

    # Most recent day with a complete feature row is the launch point, even
    # though its target (tomorrow) hasn't happened yet.
    launch = feat.dropna(subset=FEATURE_COLS)
    launch = launch[launch["day"] == launch["day"].max()]

    raw           = float(model.predict(launch[cols])[0])
    baseline      = float(launch["temp_lag1"].iloc[0])
    pred, clamped = apply_sanity_bounds(raw, baseline, train)
    target_day    = pd.Timestamp(launch["day"].iloc[0]) + pd.Timedelta(days=1)

    result.update({
        "target_day":       target_day.date().isoformat(),
        "predicted_temp_c": round(pred, 2),
        "baseline_temp_c":  round(baseline, 2),
        "clamped":          clamped,
    })

    # --- append to the prediction log (one row per forecast ever made) ---
    row = pd.DataFrame([{
        "predicted_on":     date.today().isoformat(),
        "target_day":       result["target_day"],
        "predicted_temp_c": result["predicted_temp_c"],
        "raw_model_temp_c": round(raw, 2),
        "clamped":          clamped,
        "baseline_temp_c":  result["baseline_temp_c"],
        "trained_rows":     result["trained_rows"],
        "n_features":       len(cols),
        "seasonal_used":    result["seasonal_used"],
        "model":            "RidgeCV(standardised)",
    }])

    if os.path.exists(PREDICTIONS_CSV):
        prev = pd.read_csv(PREDICTIONS_CSV)
        # Re-running on the same day should overwrite, not duplicate.
        prev = prev[prev["predicted_on"] != row["predicted_on"].iloc[0]]
        row  = pd.concat([prev, row], ignore_index=True)
    row.to_csv(PREDICTIONS_CSV, index=False)

    # --- append metrics history so accuracy is trackable over time ---
    if metrics:
        mrow = pd.DataFrame([{"run_date": date.today().isoformat(), **metrics}])
        if os.path.exists(METRICS_CSV):
            prevm = pd.read_csv(METRICS_CSV)
            prevm = prevm[prevm["run_date"] != mrow["run_date"].iloc[0]]
            mrow  = pd.concat([prevm, mrow], ignore_index=True)
        mrow.to_csv(METRICS_CSV, index=False)

    print(f"Forecast for {result['target_day']}: {result['predicted_temp_c']} C "
          f"(persistence baseline {result['baseline_temp_c']} C)")
    print(f"  features: {len(cols)} "
          f"({'seasonal ON' if result['seasonal_used'] else 'seasonal OFF — not enough annual coverage'})")
    if clamped:
        print(f"  WARNING: raw model output {raw:.2f} C was outside physical "
              f"bounds and was clamped to {pred:.2f} C.")
    if metrics:
        print(f"  backtest over {metrics['n_scored_days']} days — "
              f"model MAE {metrics['model_mae_c']} C vs "
              f"persistence MAE {metrics['baseline_mae_c']} C "
              f"(skill {metrics['skill_vs_persistence']:+.1%})")

    return result
