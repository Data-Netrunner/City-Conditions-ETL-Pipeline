import requests
import pandas as pd


def fetch_weather_hourly(lat: float, lon: float, timezone: str, past_days: int = 7) -> pd.DataFrame:
    """
    Pull past N days of hourly weather from Open-Meteo.
    Returns: ts, temperature_c, precipitation_mm, windspeed_kmh
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":  lat,
        "longitude": lon,
        "hourly":    "temperature_2m,precipitation,windspeed_10m",
        "past_days": past_days,
        "timezone":  timezone,
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    j = r.json()

    hourly = j["hourly"]
    df = pd.DataFrame({
        "ts":               pd.to_datetime(hourly["time"]),
        "temperature_c":    hourly["temperature_2m"],
        "precipitation_mm": hourly["precipitation"],
        "windspeed_kmh":    hourly["windspeed_10m"],
    })

    return df
