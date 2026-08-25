"""
Builds the README's prediction block.

Kept in its own module so update_readme_weather.py only needs a three-line
change rather than a rewrite.
"""


def prediction_section_lines(prediction: dict | None) -> list[str]:
    """Return the markdown lines for the forecast + accuracy section."""
    if not prediction or prediction.get("predicted_temp_c") is None:
        return []

    m = prediction.get("metrics") or {}
    lines = []

    lines.append("## Next-Day Forecast (model output)\n\n")
    lines.append(
        f"- Forecast for **{prediction['target_day']}**: "
        f"**{prediction['predicted_temp_c']} °C** average temperature\n"
    )
    lines.append(
        f"- Persistence baseline (\"same as today\"): "
        f"{prediction['baseline_temp_c']} °C\n"
    )
    lines.append(
        f"- Model: RidgeCV on 10 engineered features, "
        f"trained on {prediction['trained_rows']} observed days\n\n"
    )

    if m:
        skill = m.get("skill_vs_persistence")
        verdict = (
            "beating the baseline" if skill is not None and skill > 0
            else "not yet beating the baseline"
        )

        lines.append("### Accuracy (walk-forward backtest)\n\n")
        lines.append(
            "Every forecast below was made using only data available *before* "
            "the day it predicts — no future information leaks into training.\n\n"
        )
        lines.append("| Metric | Model | Persistence baseline |\n")
        lines.append("|---|---|---|\n")
        lines.append(f"| MAE (°C) | **{m['model_mae_c']}** | {m['baseline_mae_c']} |\n")
        lines.append(f"| RMSE (°C) | **{m['model_rmse_c']}** | {m['baseline_rmse_c']} |\n")
        lines.append(f"| Days scored | {m['n_scored_days']} | {m['n_scored_days']} |\n\n")

        if skill is not None:
            lines.append(
                f"**Skill score vs persistence: {skill:+.1%}** — currently {verdict}. "
                "Skill is the share of the baseline's error the model removes; "
                "it is published whether it is positive or negative.\n\n"
            )

        lines.append("![Forecast vs Actual](reports/charts/forecast_vs_actual_30d.png)\n\n")
        lines.append("![Forecast Error](reports/charts/forecast_error_30d.png)\n\n")

    lines.append("---\n\n")
    return lines
