# National Weather Big Data Analytics

A local Streamlit workspace for cleaning station observations, reviewing climatology, summarizing station networks, and flagging descriptive trend deviations.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run src/app.py
# Or: python run.py
```

## Data sources

- **Synthetic station network:** deterministic, fictional observations; works offline.
- **CSV upload:** required fields are station, timestamp/date, and temperature in °C. Common aliases such as `station_id`, `datetime`, `temperature_c`, `rainfall_mm`, and `wind_speed_ms` are supported. Humidity, pressure, wind, and precipitation are optional.
- Uploads are limited to 10 MB and 100,000 rows. Invalid required records are excluded, optional out-of-range values become missing, and duplicate station/timestamp pairs keep the last record.
- Export the cleaned observations and a JSON analytics report from the dashboard.

Generate a local CSV and SQLite database:

```bash
python scripts/generate_demo_data.py
```

## CSV pipeline and API

```python
from src.weather import run_pipeline
report = run_pipeline("data/sample/weather.csv", db_path="data/sample/analytics.db")
print(report)
```

Run the optional API with `uvicorn src.api:app --reload`. It exposes `GET /health`, `GET /climatology/demo`, and `POST /analytics/summary` with an `observations` JSON array (up to 10,000 records).

## Checks

```bash
python -m pip install -r requirements-dev.txt
pytest -v
ruff check src run.py tests
```

## Limitations

The bundled data is synthetic. Trend anomalies are descriptive, not forecasts; benchmark timings depend on the local sample and installed engines. Validate against trusted station feeds and domain expertise before operational use.

## License

MIT
