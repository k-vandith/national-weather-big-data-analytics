# National Weather Big Data Analytics

![Weather Atlas logo](web/assets/weather-atlas-logo.svg)

A local-first station-weather analytics workspace built with **HTML, CSS, JavaScript, Python, FastAPI, Pandas, NumPy, and SQLite**. Import station CSVs, inspect temperature and precipitation summaries, review daily trend deviations, export cleaned data, and optionally persist observations in a local SQLite archive.

> **Important:** the built-in dataset is synthetic. This project performs descriptive analytics; it is not a numerical weather-prediction model and does not issue official weather alerts.

## Features

- **Task-focused web UI:** plain HTML, CSS, and vanilla JavaScript, split into dedicated Overview, Import, Station Network, Quality Review, and Local Archive pages. No Streamlit, Plotly, CDN, external fonts, or browser chart library required.
- **Weather Atlas branding:** the responsive interface, favicon, and README use the same theme-matched SVG mark.
- **Offline demo:** repeatable hourly sample observations for three demo stations.
- **CSV import and validation:** common station/weather column aliases, timestamp parsing, plausible temperature bounds, optional measurement validation, duplicate station/timestamp handling, 10 MB upload limit, and a 100,000-row limit.
- **Climatology summaries:** mean, minimum, maximum, 95th percentile, and recorded precipitation.
- **Visual trend review:** a native SVG chart draws daily values and a linear trend. Trend deviations are descriptive residuals, not forecasts.
- **Station network:** per-station observation counts, mean temperature, and total precipitation.
- **Exports:** cleaned CSV and a JSON analytics report.
- **Local persistence:** explicitly save the current dataset to SQLite, using station/timestamp upserts so repeat saves do not create duplicate observations.
- **JSON API:** health, sample data, CSV analysis, database summary, and database export endpoints.

## Quick start

Requirements: Python 3.11 or newer.

### Windows PowerShell

```powershell
git clone https://github.com/k-vandith/national-weather-big-data-analytics.git
cd national-weather-big-data-analytics
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
```

### macOS / Linux

```bash
git clone https://github.com/k-vandith/national-weather-big-data-analytics.git
cd national-weather-big-data-analytics
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8501**. The default server binds to loopback, so it is intended for use on the local machine.

To choose a different port:

```bash
python run.py --port 8502
```

Run Uvicorn directly if preferred:

```bash
python -m uvicorn src.api:app --host 127.0.0.1 --port 8501 --reload
```

Interactive API documentation is available at **http://127.0.0.1:8501/docs** and the OpenAPI schema at **http://127.0.0.1:8501/openapi.json**.

## Workspace pages

The app has dedicated task pages so import controls, station tables, data-quality review, and persistence tools do not crowd the overview. Use the sidebar to switch pages; the local dataset remains in browser memory while moving between views.

| Page | Local route | What it is for |
| --- | --- | --- |
| Overview | `/` | Dataset coverage, key statistics, and the daily trend chart |
| Import data | `/import` | Generate a synthetic sample, choose a CSV, validate/clean it, or download a template |
| Station network | `/network` | Filter stations, compare the station rollup, and inspect recent observations |
| Quality review | `/quality` | Adjust the residual threshold and inspect deviations from a fitted linear trend |
| Local archive | `/archive` | Explicitly save the current dataset to SQLite, refresh archive stats, or export the archive |

### Typical workflow

1. Open **Import data** and load the demo observations, or select **Analyze CSV** to validate your own station data.
2. Visit **Overview** for a summary of the active dataset. Choose a metric in the top bar to update the chart and derived summaries.
3. Use **Station network** to focus on a station and compare readings, or **Quality review** to inspect residuals. A “No deviations” result means no daily point crossed the configured threshold; it is not a statement that all source data is error-free.
4. Use **Export report** for a JSON summary or **CSV** for cleaned observations.
5. To keep the observations on disk, visit **Local archive** and select **Save current dataset**. **Refresh archive** queries the stored totals, and **Download archive CSV** exports all saved records.

The downloadable template uses canonical column names. Uploads are processed locally; they are not sent to an external weather service.

## CSV format and cleaning

Required columns:

| Canonical field | Accepted aliases | Meaning |
| --- | --- | --- |
| `station` | `station_id`, `site_id`, `station_code`, `site` | Station identifier |
| `ts` | `timestamp`, `date`, `datetime`, `time`, `observation_time`, `valid_time` | Observation timestamp |
| `temp_c` | `temperature_c`, `temperature`, `air_temp_c`, `temperature_2m` | Temperature in Celsius |

Optional fields:

| Canonical field | Accepted aliases | Expected range |
| --- | --- | --- |
| `humidity` | `humidity_pct`, `relative_humidity`, `relative_humidity_pct` | 0–100% |
| `pressure_hpa` | `pressure`, `station_pressure_hpa`, `sea_level_pressure_hpa` | 500–1200 hPa |
| `wind_ms` | `wind_speed`, `wind_speed_ms`, `wind_speed_m_s` | 0–150 m/s |
| `precip_mm` | `precipitation_mm`, `rainfall_mm`, `precipitation`, `rain_mm` | 0–2000 mm |

Column names are normalized case-insensitively. Rows without a usable station, timestamp, or temperature in **−90°C to 60°C** are excluded. Invalid optional measurements become missing values. Duplicate station/timestamp pairs retain the last occurrence. A CSV may contain up to **100,000 rows** and **10 MB**; analysis requires at least one valid observation after cleaning.

## HTTP API

All routes use the same local origin as the web interface. CSV endpoints accept the raw CSV in the request body with `Content-Type: text/csv`.

| Method and route | Purpose |
| --- | --- |
| `GET /` | Serve the dashboard HTML |
| `GET /styles.css` | Serve local styles |
| `GET /app.js` | Serve the browser application |
| `GET /assets/weather-atlas-logo.svg` | Serve the Weather Atlas logo and favicon |
| `GET /import`, `/network`, `/quality`, `/archive` | Serve direct-linkable task pages |
| `GET /api/health` | Health check for the frontend |
| `GET /api/sample?rows=1200` | Generate sample observations as JSON (1–5,000 rows) |
| `GET /api/template.csv?rows=48` | Download a sample CSV (5–5,000 rows) |
| `POST /api/analyze/csv` | Validate and analyze a CSV without saving it |
| `POST /api/ingest/csv` | Validate and upsert CSV observations into the project-local database |
| `GET /api/stored/summary` | Return stored row/station counts and station aggregates |
| `GET /api/stored.csv` | Download all database observations as CSV |
| `GET /health` | Compatibility health route |
| `GET /climatology/demo` | Compatibility synthetic climatology endpoint |
| `POST /analytics/summary` | Compatibility JSON endpoint; body contains an `observations` array of up to 10,000 objects |

Example: analyze a CSV using curl (replace the file path as needed):

```bash
curl -X POST "http://127.0.0.1:8501/api/analyze/csv" \
  -H "Content-Type: text/csv" \
  --data-binary "@weather-stations.csv"
```

Example JSON request to the compatibility summary endpoint:

```bash
curl -X POST "http://127.0.0.1:8501/analytics/summary" \
  -H "Content-Type: application/json" \
  -d '{"observations":[{"station":"STN-A","ts":"2025-01-01T00:00:00Z","temp_c":18,"precip_mm":1.2}]}'
```

CSV analysis returns `ok`, source, input/cleaned row counts, a summary object, and normalized `observations`. Invalid CSV and missing required fields return HTTP 422; uploads above 10 MB return HTTP 413.

## Python pipeline and SQLite

Generate the sample CSV and a SQLite database:

```bash
python scripts/generate_demo_data.py
```

Process a CSV programmatically and optionally persist it:

```python
from src.weather import run_pipeline

report = run_pipeline(
    "data/sample/weather.csv",
    db_path="data/sample/analytics.db",
)
print(report["observations"], report["station_count"])
print(report["temperature_c"])
```

The local web app stores data at `data/weather.db`. It only writes when **Save current dataset** is selected (or the ingestion endpoint is called). The database is a local working artifact and should be backed up or deleted according to your own data-retention needs.

## Development and tests

Install the development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run checks from the repository root:

```bash
ruff check src run.py tests
node --check web/app.js
bandit -q -r src run.py -ll
pip-audit -r requirements.txt --progress-spinner off
pytest -v
```

The CI workflow runs linting, JavaScript syntax validation, Bandit, dependency auditing, and all tests.

## Repository structure

```
web/
  index.html       Dashboard markup
  styles.css       Responsive visual system
  app.js           Browser-side state, page routing, charting, import/export
  assets/
    weather-atlas-logo.svg  Theme-matched logo and favicon
src/
  api.py           FastAPI static and data routes
  weather.py       CSV cleaning, SQLite, aggregation, baseline pipeline
  weather_features.py
                  Climatology, trend analysis, benchmarks, compatibility API
scripts/
  generate_demo_data.py
tests/
  test_weather.py
  test_weather_features.py
  test_weather_api.py
  test_ui_smoke.py
```

## Limitations and responsible interpretation

- Synthetic values are fictional and should not be presented as observed national weather.
- Linear trend and residual-based anomaly flags are exploratory descriptive statistics. They do not identify the cause of an outlier or predict future conditions.
- The project does not currently ingest a real-time meteorological feed or perform physical weather simulation.
- Uploaded station metadata and measurements are only as reliable as their source. Validate units, calibration, station locations, timestamps, and quality-control rules before research or operational use.
- The app is designed to bind locally by default. Do not expose an unauthenticated development server to the public internet.

## License

MIT
