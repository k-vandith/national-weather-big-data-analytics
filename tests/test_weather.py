from __future__ import annotations

import io
import sqlite3

import pandas as pd
import pytest

from src.weather import (
    MAX_UPLOAD_BYTES,
    aggregate,
    anomalies,
    generate_sample,
    ingest,
    load_weather_csv,
    normalize_observations,
    run_pipeline,
)


def test_generate_sample_is_deterministic_and_has_weather_fields() -> None:
    first = generate_sample(90, seed=8)
    second = generate_sample(90, seed=8)
    assert len(first) == 90
    assert set(("station", "ts", "temp_c", "humidity", "pressure_hpa", "wind_ms", "precip_mm")) <= set(first.columns)
    pd.testing.assert_frame_equal(first, second)


@pytest.mark.parametrize("n", [0, -1, 1.5, True, 1_000_001])
def test_generate_sample_rejects_invalid_size(n: object) -> None:
    with pytest.raises(ValueError, match="integer"):
        generate_sample(n=n)  # type: ignore[arg-type]


def test_normalize_aliases_filters_bad_required_rows_and_deduplicates() -> None:
    raw = pd.DataFrame({
        "station_id": [" STN-1 ", "STN-1", "STN-2", ""],
        "datetime": ["2025-01-01 00:00", "2025-01-01 00:00", "2025-01-01 01:00", "2025-01-01 02:00"],
        "temperature_c": [20, 22, 150, 18],
        "rainfall_mm": [1, 2, 3, 4],
        "humidity_pct": [50, 120, 60, 70],
        "wind_speed_ms": [3, 4, -1, 5],
    })
    clean = normalize_observations(raw)
    assert len(clean) == 1
    assert clean.loc[0, "station"] == "STN-1"
    assert clean.loc[0, "temp_c"] == 22
    assert clean.loc[0, "precip_mm"] == 2
    assert pd.isna(clean.loc[0, "humidity"])
    assert clean.loc[0, "wind_ms"] == 4


def test_normalize_requires_mandatory_fields_and_rejects_alias_collisions() -> None:
    with pytest.raises(ValueError, match="Missing required"):
        normalize_observations(pd.DataFrame({"station": ["A"], "temperature_c": [20]}))
    with pytest.raises(ValueError, match="multiple columns for temp_c"):
        normalize_observations(pd.DataFrame({
            "station": ["A"],
            "ts": ["2025-01-01"],
            "temp_c": [20],
            "temperature_c": [21],
        }))


def test_load_weather_csv_and_size_limit() -> None:
    raw = b"station_id,timestamp,temperature_c\nA,2025-01-01,21.5\n"
    frame = load_weather_csv(raw)
    assert list(frame.columns) == ["station_id", "timestamp", "temperature_c"]
    with pytest.raises(ValueError, match="10 MB"):
        load_weather_csv(b"x" * (MAX_UPLOAD_BYTES + 1))


def test_file_like_csv_enforces_byte_limit_and_restores_cursor() -> None:
    oversized = io.BytesIO(b"x" * (MAX_UPLOAD_BYTES + 1))
    with pytest.raises(ValueError, match="10 MB"):
        load_weather_csv(oversized)
    assert oversized.tell() == 0


def test_csv_loader_enforces_row_limit_before_unbounded_parse() -> None:
    payload = ("station,ts,temp_c\\n" + "A,2025-01-01,20\\n" * 100_001).encode("ascii")
    with pytest.raises(ValueError, match="100000 rows"):
        load_weather_csv(payload)


def test_csv_loader_normalizes_empty_file_exception() -> None:
    with pytest.raises(ValueError, match="no observations"):
        load_weather_csv(b"")


def test_station_precipitation_is_null_when_no_measurements_exist() -> None:
    from src.weather import summarize_observations

    frame = pd.DataFrame({
        "station": ["A", "A", "B"],
        "ts": ["2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z", "2025-01-01T00:00:00Z"],
        "temp_c": [10, 11, 12],
        "precip_mm": [float("nan"), float("nan"), float("nan")],
    })

    summary = summarize_observations(frame)

    assert summary["total_precip_mm"] is None
    assert {item["station"]: item["total_precip_mm"] for item in summary["by_station"]} == {"A": None, "B": None}


def test_ingest_is_idempotent_and_aggregates_station_metrics(tmp_path) -> None:
    db = tmp_path / "nested" / "weather.db"
    first = pd.DataFrame({
        "station": ["A", "A", "B"],
        "ts": ["2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"],
        "temp_c": [20, 22, 18],
        "precip_mm": [1, 2, 0.5],
    })
    assert ingest(first, db) == 2
    assert ingest(first.iloc[[1, 2]], db) == 2
    rollup = aggregate(db).set_index("station")
    assert rollup.loc["A", "n"] == 1
    assert rollup.loc["A", "avg_temp"] == 22
    assert rollup.loc["A", "total_precip"] == 2
    assert rollup.loc["B", "n"] == 1
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 2


def test_aggregate_empty_db_returns_stable_schema(tmp_path) -> None:
    result = aggregate(tmp_path / "empty.db")
    assert list(result.columns) == ["station", "avg_temp", "total_precip", "n"]
    assert result.empty


def test_anomalies_detect_spike_and_ignore_constant_series(tmp_path) -> None:
    db = tmp_path / "anomalies.db"
    frame = pd.DataFrame({
        "station": ["A"] * 6,
        "ts": pd.date_range("2025-01-01", periods=6, freq="h").astype(str),
        "temp_c": [10, 11, 9, 10, 10, 59],
    })
    ingest(frame, db)
    result = anomalies(db, z=2)
    assert len(result) == 1
    assert result.iloc[0]["temp_c"] == 59
    constant_db = tmp_path / "constant.db"
    ingest(frame.assign(temp_c=15), constant_db)
    assert anomalies(constant_db).empty


@pytest.mark.parametrize("threshold", [0, -1, float("nan")])
def test_anomalies_reject_invalid_threshold(tmp_path, threshold: float) -> None:
    with pytest.raises(ValueError, match="positive finite"):
        anomalies(tmp_path / "bad.db", z=threshold)


def test_run_pipeline_cleans_summarizes_and_persists_csv(tmp_path) -> None:
    csv = tmp_path / "station.csv"
    pd.DataFrame({
        "station_id": ["A", "A", "B", "B"],
        "datetime": ["2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z", "not-a-date", "2025-01-01T02:00:00Z"],
        "temperature_c": [20, 22, 18, 17],
        "rainfall_mm": [0, 1.5, 2.0, 3.0],
    }).to_csv(csv, index=False)
    summary = run_pipeline(csv, db_path=tmp_path / "loaded.db")
    assert summary["source_file"] == "station.csv"
    assert summary["rows_read"] == 4
    assert summary["rows_removed"] == 2
    assert summary["rows_upserted"] == 2
    assert summary["station_count"] == 2
    assert summary["observations"] == 2
    assert summary["temperature_c"]["mean"] == 19.5
    assert len(summary["by_station"]) == 2


def test_run_pipeline_missing_file_and_invalid_csv(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        run_pipeline(tmp_path / "missing.csv")
    csv = tmp_path / "invalid.csv"
    pd.DataFrame({"station": ["A"], "humidity": [50]}).to_csv(csv, index=False)
    with pytest.raises(ValueError, match="Missing required"):
        run_pipeline(csv)
