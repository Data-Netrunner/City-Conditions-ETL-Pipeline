"""
Next-day average temperature forecasting.

Design notes (these are the interview talking points):

1. OBSERVED DATA ONLY. Open-Meteo's forecast endpoint returns past days AND
   future days in the same payload. Training a "next-day" model on rows that
   are themselves Open-Meteo forecasts is target leakage: the model would just
   learn to copy the API. Everything here reads the observed-only history file.

2. RIDGE, NOT A FOREST. At n~50 daily rows a tree ensemble overfits, and more
   importantly trees cannot extrapolate: a RandomForest trained through June
   can never predict a colder-than-training-set January. Temperature has real
   trend and seasonality, so a regularised linear model is the honest choice
   at this sample size.

3. BASELINE OR IT DIDN'T HAPPEN. Every metric is reported next to persistence
   ("tomorrow = today"), which is a surprisingly strong weather baseline.
   A model that cannot beat persistence has no value, and saying so out loud
   is the point of the accuracy report.

4. WALK-FORWARD VALIDATION. A random train/test split on a time series leaks
   the future into the past. Scoring here is expanding-window: to score day i,
   fit only on days < i.
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

# Features fed to the model. All are derived from days <= d to predict day d+1.
FEATURE_COLS = [
    "temp_lag1", "temp_lag2", "temp_lag3",
    "temp_roll3", "temp_roll7",
    "temp_delta1",
    "precip_lag1", "wind_lag1",
    "doy_sin", "doy_cos",
]

MIN_TRAIN_ROWS = 15   # below this there is not enough history to fit anything


# ----------------------------------------------------------------------------
# 1. Load observed daily history
# ----------------------------------------------------------------------------
def load_daily_observed(location_id: int = 1) -> pd.DataFrame:
    """
    Read the accumulated daily observation history.

    This deliberately reads the committed history file rather than the
    warehouse: the warehouse only ever holds Open-Meteo's rolling window, so
    querying it directly caps the model at ~2 weeks of training data no matter
    how long the pipeline has been running.
    """
    return load_daily_history(location_id)


# ----------------------------------------------------------------------------
# 2. Feature engineering
# ----------------------------------------------------------------------------
def build_features(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Turn the daily series into a supervised learning table.

    One row per day d, with:
      - features built only from information available on day d
      - target = the observed average temperature on day d + 1

    The history has calendar gaps (the pipeline only ever held a rolling window
    before history was made durable). Reindexing onto a complete daily calendar
    first means lags that span a gap come out as NaN and get dropped, rather
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


def _new_model():
    """
    RidgeCV picks its own regularisation strength by cross-validation, so there
    is no hand-tuned magic number in the pipeline. Scaling first matters: ridge
    penalises large coefficients, and the raw features are on wildly different
    scales (degrees vs. mm vs. sine waves).
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
    Expanding-window validation. For each day i past the warm-up period, fit on
    days 0..i-1 only and predict day i. This is the only way to get an honest
    error estimate on a time series.

    Returns one row per scored day, model prediction and baseline side by side.
    """
    rows = []
    if len(train) <= min_train:
        return pd.DataFrame(rows)

    X = train[FEATURE_COLS].to_numpy()
    y = train["target_temp_c"].to_numpy()

    for i in range(min_train, len(train)):
        model = _new_model()
        model.fit(X[:i], y[:i])
        pred = float(model.predict(X[i:i + 1])[0])

        rows.append({
            "target_day":       train.loc[i, "target_day"],
            "actual_temp_c":    float(y[i]),
            "predicted_temp_c": pred,
            # Persistence baseline: "tomorrow will be like today".
            "baseline_temp_c":  float(train.loc[i, "temp_lag1"]),
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

    # Skill score: the fraction of the baseline's error the model removes.
    # Positive = better than persistence, negative = worse. Publishing this
    # honestly is the whole point of the section.
    skill = (base_mae - model_mae) / base_mae if base_mae > 0 else float("nan")

    return {
        "n_scored_days":         int(len(bt)),
        "model_mae_c":           round(model_mae, 3),
        "model_rmse_c":          round(model_rmse, 3),
        "baseline_mae_c":        round(base_mae, 3),
        "baseline_rmse_c":       round(base_rmse, 3),
        "skill_vs_persistence":  round(skill, 3),
    }


# ----------------------------------------------------------------------------
# 4. Predict tomorrow + persist outputs
# ----------------------------------------------------------------------------
def predict_next_day(location_id: int = 1) -> dict:
    """
    Full prediction step. Returns a dict the README writer consumes.
    Degrades gracefully: too little history simply skips the forecast rather
    than crashing the pipeline.
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
    model = _new_model()
    model.fit(train[FEATURE_COLS], train["target_temp_c"])

    # The most recent day with a complete feature row is the launch point,
    # even though its target (tomorrow) hasn't happened yet.
    launch = feat.dropna(subset=FEATURE_COLS)
    launch = launch[launch["day"] == launch["day"].max()]

    pred       = float(model.predict(launch[FEATURE_COLS])[0])
    target_day = pd.Timestamp(launch["day"].iloc[0]) + pd.Timedelta(days=1)
    baseline   = float(launch["temp_lag1"].iloc[0])

    result.update({
        "target_day":       target_day.date().isoformat(),
        "predicted_temp_c": round(pred, 2),
        "baseline_temp_c":  round(baseline, 2),
    })

    # --- append to the prediction log (one row per forecast ever made) ---
    row = pd.DataFrame([{
        "predicted_on":     date.today().isoformat(),
        "target_day":       result["target_day"],
        "predicted_temp_c": result["predicted_temp_c"],
        "baseline_temp_c":  result["baseline_temp_c"],
        "trained_rows":     result["trained_rows"],
        "model":            "RidgeCV(standardised, 10 features)",
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
    if metrics:
        print(f"Backtest over {metrics['n_scored_days']} days — "
              f"model MAE {metrics['model_mae_c']} C vs "
              f"persistence MAE {metrics['baseline_mae_c']} C "
              f"(skill {metrics['skill_vs_persistence']:+.1%})")

    return result
