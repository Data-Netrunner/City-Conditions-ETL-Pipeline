import pandas as pd

def clean_weather(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # Ensure correct types
    out["ts"] = pd.to_datetime(out["ts"], errors="coerce")

    # Drop rows with bad timestamps
    out = out.dropna(subset=["ts"])

    # Basic sanity rules
    out.loc[(out["temperature_c"] < -60) | (out["temperature_c"] > 60), "temperature_c"] = None
    out.loc[out["precipitation_mm"] < 0, "precipitation_mm"] = None
    out.loc[out["windspeed_kmh"] < 0, "windspeed_kmh"] = None

    # Deduplicate on timestamp (Open-Meteo should be unique, but we enforce it)
    out = out.drop_duplicates(subset=["ts"])

    # Sort ascending by time
    out = out.sort_values("ts").reset_index(drop=True)

    return out
