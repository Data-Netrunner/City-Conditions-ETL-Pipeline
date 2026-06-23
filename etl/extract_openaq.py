import requests
import pandas as pd


def fetch_air_quality_hourly(lat: float, lon: float, timezone: str, past_days: int = 7) -> pd.DataFrame:
    """
    Pull past N days of hourly air quality from Open-Meteo Air Quality API.
    Returns: ts, pm25, pm10, no2, o3
    """
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude":  lat,
        "longitude": lon,
        "hourly":    "pm2_5,pm10,nitrogen_dioxide,ozone",
        "past_days": past_days,
        "timezone":  timezone,
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    j = r.json()

    h = j["hourly"]
    df = pd.DataFrame({
        "ts":   pd.to_datetime(h["time"]),
        "pm25": h.get("pm2_5"),
        "pm10": h.get("pm10"),
        "no2":  h.get("nitrogen_dioxide"),
        "o3":   h.get("ozone"),
    })

    return df
