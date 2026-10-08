from src.weather_features import climatology_stats, trend_and_anomalies, benchmark_engines, create_fastapi_app
import pandas as pd
def test_weather(tmp_path):
    df = pd.DataFrame({"station": ["A"]*50, "temp_c": list(range(50))})
    assert "mean" in climatology_stats(df)
    assert "is_anomaly" in trend_and_anomalies(df).columns
    assert "pandas_s" in benchmark_engines(df, tmp_path/"x.parquet")
    assert create_fastapi_app().title
