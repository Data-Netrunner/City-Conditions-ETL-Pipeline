import pandas as pd


def clean_air_quality(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["ts"] = pd.to_datetime(out["ts"], errors="coerce")
    out = out.dropna(subset=["ts"])

    # Remove physically impossible negatives
    for col in ["pm25", "pm10", "no2", "o3"]:
        if col in out.columns:
            out.loc[out[col] < 0, col] = None

    out = out.drop_duplicates(subset=["ts"])
    out = out.sort_values("ts").reset_index(drop=True)

    return out
