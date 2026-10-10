from __future__ import annotations

import pandas as pd
import pytest

from src.weather_features import benchmark_engines, climatology_stats, to_parquet, trend_and_anomalies


def test_climatology_stats_and_numeric_column_fallback() -> None:
    frame = pd.DataFrame({"station": ["A", "B", "C"], "temp_c": [10.0, 20.0, 30.0]})
    result = climatology_stats(frame)
    assert result["count"] == 3
    assert result["mean"] == 20
    assert result["min"] == 10
    assert result["max"] == 30
    assert result["p95"] == pytest.approx(29)
    assert climatology_stats(frame, "missing")["mean"] == 20


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame(),
        pd.DataFrame({"text": ["hot", "cold"]}),
        pd.DataFrame({"temp_c": [float("nan"), float("inf")]}),
    ],
)
def test_climatology_rejects_empty_or_non_numeric_data(frame: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        climatology_stats(frame)


def test_trend_and_anomalies_produces_finite_trend_columns() -> None:
    frame = pd.DataFrame({"station": ["A"] * 6, "temp_c": [10, 11, 9, 10, 10, 100]})
    result = trend_and_anomalies(frame, anomaly_sigma=1.5)
    assert {"trend", "anomaly", "anomaly_zscore", "is_anomaly"} <= set(result.columns)
    assert result["trend"].map(lambda v: pd.notna(v) and abs(v) < 200).all()
    assert result["is_anomaly"].any()
    with pytest.raises(ValueError, match="anomaly_sigma"):
        trend_and_anomalies(frame, anomaly_sigma=0)


def test_benchmark_reports_pandas_even_without_optional_engines(tmp_path) -> None:
    frame = pd.DataFrame({"station": ["A", "A", "B"], "temp_c": [10, 12, 15]})
    result = benchmark_engines(frame, tmp_path / "subdir" / "bench.parquet")
    assert result["pandas_s"] >= 0
    assert (tmp_path / "subdir" / "bench.csv").exists()


def test_benchmark_rejects_empty_input(tmp_path) -> None:
    with pytest.raises(ValueError, match="rows and columns"):
        benchmark_engines(pd.DataFrame(), tmp_path / "bench.parquet")


def test_to_parquet_has_explicit_csv_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    frame = pd.DataFrame({"temp_c": [1, 2]})

    def no_engine(self, *args, **kwargs):
        raise ImportError("no parquet engine installed")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", no_engine)
    output = to_parquet(frame, tmp_path / "output.parquet")
    assert output.suffix == ".csv"
    assert pd.read_csv(output)["temp_c"].tolist() == [1, 2]
