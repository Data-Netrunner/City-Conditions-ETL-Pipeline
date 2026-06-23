import pandas as pd


def clean_weather(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["ts"] = pd.to_datetime(out["ts"], errors="coerce")
    out = out.dropna(subset=["ts"])

    # Sanity bounds
    out.loc[(out["temperature_c"] < -60) | (out["temperature_c"] > 60), "temperature_c"] = None
    out.loc[out["precipitation_mm"] < 0, "precipitation_mm"] = None
    out.loc[out["windspeed_kmh"]    < 0, "windspeed_kmh"]    = None

    out = out.drop_duplicates(subset=["ts"])
    out = out.sort_values("ts").reset_index(drop=True)

    return out
