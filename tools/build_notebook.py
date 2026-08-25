"""
Generate city_conditions_pipeline.ipynb directly from the repo's source files.

WHY THIS EXISTS
---------------
The notebook used to be a hand-maintained transcription of every etl/*.py file.
That works exactly once. The moment a module changes, the notebook silently
becomes a description of a pipeline that no longer exists — and a reviewer
opening it gets a different story than the code tells.

So the notebook is a DERIVED ARTIFACT now. Every code cell is read straight off
disk at build time, which means it cannot drift: if the source changes and this
script is re-run, the notebook changes with it. The prose lives here, next to
the file list it describes.

Usage:
    python tools/build_notebook.py
    python tools/build_notebook.py --check   # CI: fail if the notebook is stale
"""

import argparse
import json
import os
import sys

NOTEBOOK_PATH = "city_conditions_pipeline.ipynb"

# (source file, section heading, explanatory prose)
SECTIONS = [
    (
        "etl/config.py",
        "1. Configuration",
        "All location settings and file paths live in one place. To point this "
        "pipeline at a different city, this is the only file that changes.",
    ),
    (
        "etl/extract_weather.py",
        "2. Extract — Weather",
        "Pulls hourly weather from the Open-Meteo Forecast API. No API key "
        "required.\n\n"
        "**Note `forecast_days=0`.** Open-Meteo returns past *and* future days "
        "in a single payload, defaulting to 7 forecast days. Loading those "
        "future rows into the observations table would store model output as "
        "measurement — and would hand a next-day forecasting model the answer "
        "it is supposed to predict. That is target leakage, and this parameter "
        "is what prevents it.",
    ),
    (
        "etl/extract_openaq.py",
        "3. Extract — Air Quality",
        "Pulls hourly PM2.5, PM10, NO2 and ozone from the Open-Meteo Air "
        "Quality API — the standard indicators of urban air quality.",
    ),
    (
        "etl/transform_weather.py",
        "4. Transform — Weather",
        "Parses timestamps, nulls physically impossible readings (temperatures "
        "outside −60 °C to 60 °C, negative rainfall or wind), deduplicates on "
        "timestamp, and sorts chronologically.",
    ),
    (
        "etl/transform_air_quality.py",
        "5. Transform — Air Quality",
        "Same treatment for air quality: negative concentrations are physically "
        "impossible and get nulled rather than silently averaged in.",
    ),
    (
        "sql/schema.sql",
        "6. Warehouse Schema",
        "Three tables: `dim_location`, `fact_weather_hourly`, and "
        "`fact_air_quality_hourly`. Both fact tables use a composite primary "
        "key of `(location_id, ts)` — that is what makes the upsert idempotent, "
        "so running the pipeline twice in a day updates rows instead of "
        "duplicating them.\n\n"
        "`CREATE TABLE IF NOT EXISTS` makes the schema safe to re-run on every "
        "pipeline start.",
    ),
    (
        "etl/load_weather_duckdb.py",
        "7. Load — Weather",
        "`INSERT ... ON CONFLICT DO UPDATE` against DuckDB, a serverless "
        "analytical database that runs entirely from a single file.",
    ),
    (
        "etl/load_air_quality_duckdb.py",
        "8. Load — Air Quality",
        "The same upsert pattern for the air quality fact table.",
    ),
    (
        "sql/kpis_combined.sql",
        "9. KPI Query",
        "Aggregates the hourly warehouse into daily KPIs, joining weather and "
        "air quality by day, most recent 30 days first.",
    ),
    (
        "etl/history_store.py",
        "10. Durable History",
        "**This module exists because of a defect.** The pipeline only ever "
        "pulls a rolling 7-day window, and the DuckDB warehouse was not "
        "committed between CI runs — so no matter how many hundreds of times "
        "the pipeline ran, the warehouse reset to whatever was last checked in. "
        "The run log showed 200+ successes against a warehouse holding 35 days "
        "with a four-month hole in it.\n\n"
        "The fix is an append-only CSV of observed daily aggregates that *is* "
        "committed on every run. It diffs cleanly in git (unlike a binary "
        "`.duckdb`), and it demotes the warehouse to a rebuildable derived "
        "artifact rather than the only copy of the data.",
    ),
    (
        "etl/predict_temperature.py",
        "11. Prediction — Next-Day Temperature",
        "The forecasting model. Four design decisions worth calling out:\n\n"
        "1. **Observed data only.** Trains off the history file, never the "
        "warehouse's forecast rows.\n"
        "2. **RidgeCV, not a forest.** At this sample size a tree ensemble "
        "overfits, and trees cannot extrapolate at all.\n"
        "3. **Persistence baseline on every metric.** A model that cannot beat "
        "\"tomorrow will be like today\" has no value, and the skill score is "
        "published whether it is positive or negative.\n"
        "4. **Walk-forward validation.** A random train/test split on a time "
        "series leaks the future into the past.\n\n"
        "It also carries two guards added after the pipeline published a "
        "40.07 °C August forecast for Toronto: seasonal day-of-year features "
        "stay disabled until the history covers most of a year, and every "
        "prediction is bounded by a physical sanity check before publication.",
    ),
    (
        "etl/make_charts_combined.py",
        "12. Reporting — Weather & Air Quality Charts",
        "Three 30-day time-series charts. `matplotlib.use(\"Agg\")` is set "
        "explicitly because GitHub Actions runners have no display.",
    ),
    (
        "etl/make_prediction_chart.py",
        "13. Reporting — Forecast Charts",
        "Predicted vs actual vs baseline, and absolute error per day. The "
        "second chart is the one that shows *where* the model struggles rather "
        "than just how much.",
    ),
    (
        "etl/readme_prediction_section.py",
        "14. Reporting — README Forecast Block",
        "Builds the forecast and accuracy markdown, including the disclosure "
        "lines about disabled seasonal features and any clamping applied.",
    ),
    (
        "etl/update_readme_weather.py",
        "15. Reporting — README Rewrite",
        "Regenerates the README on every run so the published numbers can never "
        "be stale relative to the data.",
    ),
    (
        "etl/data_quality.py",
        "16. Data Quality & Run Logging",
        "Validation helpers that fail loudly before bad data reaches the "
        "warehouse, plus an append to `reports/run_log.csv` on every run — "
        "success or failure — giving a full history of pipeline health.",
    ),
    (
        "etl/run_weather_pipeline.py",
        "17. Main Pipeline Entry Point",
        "What GitHub Actions calls every morning. Orchestrates every step "
        "above, wrapped in try/except so a failure is logged to the run log "
        "before the error re-raises and turns the Actions run red.",
    ),
    (
        ".github/workflows/daily_weather_etl.yml",
        "18. Automation — Daily ETL Workflow",
        "Runs at 11:10 UTC (~7:10 AM Toronto) and on manual dispatch.\n\n"
        "The `git add README.md reports data/history` line is load-bearing: "
        "without `data/history` the observation record is regenerated and "
        "discarded on every run, and the model's training set never grows.",
    ),
    (
        ".github/workflows/tests.yml",
        "19. Automation — CI Test Suite",
        "Runs pytest on every push and pull request.",
    ),
]

TEST_FILES = [
    ("tests/test_transforms.py", "Transform invariants"),
    ("tests/test_features.py", "Feature engineering — including the no-leakage-across-gaps property"),
    ("tests/test_prediction_guards.py", "Regression tests for both extrapolation guards"),
    ("tests/test_history_and_quality.py", "History upsert semantics and the data-quality gate"),
]


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text, executed=False):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


def read(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read().rstrip("\n")


def build():
    cells = []

    cells.append(md(
        "# City Conditions ETL Pipeline\n"
        "### Daily weather + air quality analytics with next-day forecasting — Toronto, Canada\n"
        "\n"
        "This notebook documents the full pipeline behind the "
        "[City Conditions ETL Pipeline](https://github.com/Data-Netrunner/City-Conditions-ETL-Pipeline).\n"
        "\n"
        "Every morning, GitHub Actions:\n"
        "\n"
        "1. **Extracts** hourly weather and air quality from Open-Meteo (no API key)\n"
        "2. **Transforms** it — parsing, validating, deduplicating\n"
        "3. **Loads** it into a DuckDB warehouse via idempotent upserts\n"
        "4. **Appends** observed daily aggregates to a durable, version-controlled history file\n"
        "5. **Forecasts** the next day's average temperature and scores every past forecast walk-forward\n"
        "6. **Publishes** KPIs, charts, and a rewritten README\n"
        "\n"
        "---\n"
        "\n"
        "> **This notebook is generated, not hand-written.** Every code cell below is read "
        "directly from the repository source by `tools/build_notebook.py`. Regenerate it with:\n"
        ">\n"
        "> ```bash\n"
        "> python tools/build_notebook.py\n"
        "> ```\n"
        ">\n"
        "> Doing it this way means the notebook cannot drift out of sync with the code it "
        "describes — the previous hand-maintained version had done exactly that.\n"
    ))

    cells.append(md(
        "## Dependencies\n"
        "\n"
        "The pipeline needs five libraries. In Colab, only `duckdb` is missing by default.\n"
    ))
    cells.append(code("!pip install -q duckdb pandas requests matplotlib scikit-learn"))

    missing = []
    for path, title, prose in SECTIONS:
        src = read(path)
        if src is None:
            missing.append(path)
            continue

        cells.append(md(f"---\n## {title}\n\n`{path}`\n\n{prose}\n"))
        lang = "sql" if path.endswith(".sql") else ("yaml" if path.endswith((".yml", ".yaml")) else "python")

        if lang == "python":
            cells.append(code(f"# {path}\n\n{src}"))
        else:
            # Non-Python sources go in a markdown fence — they aren't runnable cells.
            cells.append(md(f"```{lang}\n{src}\n```\n"))

    # --- test suite section ---
    cells.append(md(
        "---\n"
        "## 20. Test Suite\n"
        "\n"
        "`pytest`, run in CI on every push.\n"
        "\n"
        "The tests worth reading are the regression ones — each exists because the "
        "pipeline actually shipped the bug it guards against:\n"
        "\n"
        "- a feature builder that would pair a February day with a June day across the history gap\n"
        "- a model that published a 40.07 °C August forecast for Toronto\n"
    ))
    for path, desc in TEST_FILES:
        src = read(path)
        if src is None:
            missing.append(path)
            continue
        cells.append(md(f"**`{path}`** — {desc}\n"))
        cells.append(code(f"# {path}\n\n{src}"))

    cells.append(md(
        "---\n"
        "## Pipeline Summary\n"
        "\n"
        "| Stage | File | What it does |\n"
        "|---|---|---|\n"
        "| Config | `etl/config.py` | City coordinates and file paths |\n"
        "| Extract | `etl/extract_weather.py` | Hourly weather, observations only |\n"
        "| Extract | `etl/extract_openaq.py` | Hourly air quality |\n"
        "| Transform | `etl/transform_weather.py` | Cleans and validates weather |\n"
        "| Transform | `etl/transform_air_quality.py` | Cleans and validates air quality |\n"
        "| Load | `etl/load_weather_duckdb.py` | Idempotent upsert into DuckDB |\n"
        "| Load | `etl/load_air_quality_duckdb.py` | Idempotent upsert into DuckDB |\n"
        "| History | `etl/history_store.py` | Durable append-only observation record |\n"
        "| Predict | `etl/predict_temperature.py` | Next-day forecast + walk-forward scoring |\n"
        "| Report | `etl/make_charts_combined.py` | 30-day KPI charts |\n"
        "| Report | `etl/make_prediction_chart.py` | Forecast vs actual, error per day |\n"
        "| Report | `etl/update_readme_weather.py` | Rewrites the README |\n"
        "| Quality | `etl/data_quality.py` | Validation gate and run log |\n"
        "| Orchestrate | `etl/run_weather_pipeline.py` | Entry point |\n"
        "\n"
        "---\n"
        "\n"
        "*Built by Andre Felix — data updated daily via GitHub Actions*\n"
    ))

    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
            "colab": {"provenance": []},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return nb, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if the notebook on disk is out of date")
    args = ap.parse_args()

    nb, missing = build()
    rendered = json.dumps(nb, indent=1, ensure_ascii=False) + "\n"

    for path in missing:
        print(f"  warning: {path} not found — section skipped", file=sys.stderr)

    if args.check:
        current = read(NOTEBOOK_PATH)
        if current is None or current.rstrip("\n") != rendered.rstrip("\n"):
            print("Notebook is STALE. Run: python tools/build_notebook.py", file=sys.stderr)
            return 1
        print("Notebook is up to date.")
        return 0

    with open(NOTEBOOK_PATH, "w", encoding="utf-8") as f:
        f.write(rendered)
    print(f"Wrote {NOTEBOOK_PATH} — {len(nb['cells'])} cells "
          f"from {len(SECTIONS) + len(TEST_FILES)} source files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
