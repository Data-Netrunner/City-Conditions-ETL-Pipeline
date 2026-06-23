import duckdb
import pandas as pd


def upsert_air_quality(db_path: str, df_air: pd.DataFrame, location_id: int = 1) -> None:
    con = duckdb.connect(db_path)
    df = df_air.copy()
    df["location_id"] = location_id
    con.register("a", df)
    con.execute("""
        INSERT INTO fact_air_quality_hourly(location_id, ts, pm25, pm10, no2, o3)
        SELECT location_id, ts, pm25, pm10, no2, o3 FROM a
        ON CONFLICT(location_id, ts) DO UPDATE SET
          pm25 = excluded.pm25,
          pm10 = excluded.pm10,
          no2  = excluded.no2,
          o3   = excluded.o3
    """)
    con.close()
