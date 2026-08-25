import requests
import pandas as pd


def fetch_weather_hourly(
    lat: float,
    lon: float,
    timezone: str,
    past_days: int = 7,
    forecast_days: int = 0,
) -> pd.DataFrame:
    """
    Pull hourly weather from Open-Meteo.

    forecast_days defaults to 0 — this is deliberate and important.

    Open-Meteo's /forecast endpoint returns past days AND future days in one
    payload, and its default is 7 forecast days. Loading those future rows into
    fact_weather_hourly stores model output as if it were measurement: the
    README's "latest" KPI ends up being a forecast, and any next-day prediction
    model trained on the table is just learning to copy Open-Meteo.

    Pass forecast_days explicitly if you want the API's own forecast — but keep
    it in a separate table, not in the observations fact table.

    Returns: ts, temperature_c, precipitation_mm, windspeed_kmh
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":      lat,
        "longitude":     lon,
        "hourly":        "temperature_2m,precipitation,windspeed_10m",
        "past_days":     past_days,
        "forecast_days": forecast_days,
        "timezone":      timezone,
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
