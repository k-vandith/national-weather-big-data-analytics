<p align="center">
  <img src="web/assets/weather-atlas-logo.svg" alt="Weather Atlas logo" width="92">
</p>

<h1 align="center">Weather Atlas</h1>
<p align="center">
  <strong>See the shape of the weather.</strong><br>
  A local-first national weather analytics workspace for station observations, CSV quality checks, daily trend review, and SQLite-backed history.
</p>

<p align="center">
  <a href="https://github.com/k-vandith/national-weather-big-data-analytics/actions/workflows/tests.yml"><img src="https://github.com/k-vandith/national-weather-big-data-analytics/actions/workflows/tests.yml/badge.svg?branch=main" alt="Tests"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/UI-HTML%20%2F%20CSS%20%2F%20JS-39a99a?logo=javascript&logoColor=white" alt="HTML CSS JavaScript">
  <img src="https://img.shields.io/badge/processing-local--first-5b8066" alt="Local-first processing">
  <img src="https://img.shields.io/badge/license-MIT-64748b" alt="MIT License">
</p>

---

## What is Weather Atlas?

Weather Atlas is a local-first workspace for exploring structured weather station records. Import a station CSV, review data coverage and summary statistics, compare station-level readings, inspect daily deviations from a simple linear trend, and optionally save observations to a local SQLite archive.

- **Understand the dataset:** review observation counts, station coverage, date span, means, percentiles, and recorded precipitation.
- **Explore the time series:** chart daily metric values against a fitted linear trend, with a configurable residual threshold.
- **Review station coverage:** filter by station and compare mean temperature, rainfall totals, and recent observations.
- **Validate imports:** normalize supported column aliases, remove unusable required records, and handle duplicate station/timestamp pairs.
- **Export useful results:** download cleaned observations as CSV and an analytics summary as JSON.
- **Keep data local:** imported data is processed by the local API. The application does not send records to an external weather analytics service.
- **Save deliberately:** archive observations in the project-local SQLite database only when you choose to save.

**Important:** the built-in observations are synthetic, not measurements from a live national weather feed. Trend deviations are descriptive review signals, not forecasts, proof of sensor failure, or official weather alerts.

## Quick start

Python 3.11 or newer is recommended. Runtime dependencies are listed in `requirements.txt`; no paid API key, cloud service, GPU, external font, or browser chart library is required.

~~~bash
git clone https://github.com/k-vandith/national-weather-big-data-analytics.git
cd national-weather-big-data-analytics
python -m venv .venv
~~~

Activate the virtual environment and start the workspace.

**Windows · PowerShell**

~~~powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
~~~

**macOS · Linux**

~~~bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
~~~

Open **http://127.0.0.1:8501** in your browser. The server binds to loopback by default and is intended for local use.

To select another port:

~~~bash
python run.py --port 8502
~~~

The interactive API documentation is available at **http://127.0.0.1:8501/docs**.

## Try it in five steps

1. Open **Import data** and load the reproducible demo dataset, or choose a station CSV and select **Analyze CSV**.
2. Visit **Overview** to see the dataset summary and daily trend chart. Use the metric selector in the top bar to change the displayed weather measurement.
3. Open **Station network** to compare station coverage and review the newest observations. The station filter updates the displayed station-specific summary.
4. Go to **Quality review** to adjust the residual threshold and inspect daily deviations. A “No deviations” result means no daily point crossed that threshold; it does not guarantee that every source record is correct.
5. Open **Local archive** to save the current observations to SQLite, refresh the archived counts, or download all stored records as CSV.

Use **Export report** for a JSON summary or the CSV export action for cleaned observations. The dataset remains in the browser session while switching between the workspace pages.

## Workspace navigation

| Page | Route | Purpose |
|---|---|---|
| **Overview** | `/` | Dataset coverage, key statistics, and the daily trend chart |
| **Import data** | `/import` | Load synthetic demo records, upload/validate a CSV, or download a template |
| **Station network** | `/network` | Filter stations, compare station summaries, and inspect recent records |
| **Quality review** | `/quality` | Adjust residual sensitivity and review deviations from a linear trend |
| **Local archive** | `/archive` | Save observations to SQLite and refresh or export the local archive |

Each route can be opened directly. The navigation keeps separate tasks on separate pages rather than crowding every control and table into the overview.

## Supported inputs and outputs

| Type | Format | What Weather Atlas does |
|---|---|---|
| Station observations | CSV | Reads required station, timestamp, and temperature fields plus supported optional measurements. |
| Sample data | Generated JSON / CSV | Creates deterministic synthetic station observations for offline demonstrations. |
| Data-quality review | Daily metric series | Fits a simple linear trend and flags large residuals relative to the configured threshold. |
| Cleaned data export | CSV | Exports normalized observation columns for the selected station view. |
| Analytics report | JSON | Exports source context, metric, summary statistics, and detected daily deviations. |
| Local persistence | SQLite | Saves observations with station/timestamp upserts to avoid duplicate pairs on repeated saves. |
| Archive export | CSV | Downloads all observations stored in the project-local database. |

### CSV schema

Required canonical fields:

| Field | Accepted aliases | Meaning |
|---|---|---|
| `station` | `station_id`, `site_id`, `station_code`, `site` | Station identifier |
| `ts` | `timestamp`, `date`, `datetime`, `time`, `observation_time`, `valid_time` | Observation timestamp |
| `temp_c` | `temperature_c`, `temperature`, `air_temp_c`, `temperature_2m` | Air temperature in Celsius |

Optional fields:

| Field | Accepted aliases | Valid range |
|---|---|---|
| `humidity` | `humidity_pct`, `relative_humidity`, `relative_humidity_pct` | 0–100% |
| `pressure_hpa` | `pressure`, `station_pressure_hpa`, `sea_level_pressure_hpa` | 500–1200 hPa |
| `wind_ms` | `wind_speed`, `wind_speed_ms`, `wind_speed_m_s` | 0–150 m/s |
| `precip_mm` | `precipitation_mm`, `rainfall_mm`, `precipitation`, `rain_mm` | 0–2000 mm |

Column names are normalized case-insensitively. Rows without a usable station, timestamp, or temperature within −90°C to 60°C are excluded. Invalid optional measurements become missing values. Duplicate station/timestamp pairs keep the last occurrence.

Uploads are limited to **10 MB** and **100,000 rows**. An analysis needs at least one valid row after cleaning. Use **Download template** in the Import page to get a CSV with canonical column names.

## Architecture

~~~mermaid
flowchart TD
    User[User] --> UI[Weather Atlas HTML / CSS / JavaScript]
    UI --> Pages[Overview / Import / Network / Quality / Archive]
    Pages --> API[Local FastAPI application]
    API --> Clean[CSV validation and normalization]
    Clean --> Stats[Summary statistics and daily trend review]
    Clean --> Archive[SQLite station archive]
    Stats --> UI
    Archive --> UI
    UI --> Exports[Clean CSV / JSON report / archive CSV]
~~~

The browser UI is plain HTML, CSS, and vanilla JavaScript. FastAPI serves the UI assets and API endpoints; Pandas and NumPy support cleaning and analysis, and SQLite provides optional local persistence.

## API reference

All API routes use the same local origin as the web app. CSV endpoints expect the raw CSV file content in the request body with `Content-Type: text/csv`.

| Method and route | Purpose |
|---|---|
| `GET /` | Serve the overview page |
| `GET /import`, `/network`, `/quality`, `/archive` | Serve the directly linkable workspace pages |
| `GET /styles.css`, `GET /app.js` | Serve frontend assets |
| `GET /assets/weather-atlas-logo.svg` | Serve the logo and favicon |
| `GET /api/health` | Health check |
| `GET /api/sample?rows=1200` | Generate synthetic observations (1–5,000 rows) |
| `GET /api/template.csv?rows=48` | Download a template CSV (5–5,000 rows) |
| `POST /api/analyze/csv` | Clean and analyze a CSV without saving it |
| `POST /api/ingest/csv` | Clean and upsert CSV observations into SQLite |
| `GET /api/stored/summary` | Return archived row/station counts and station aggregates |
| `GET /api/stored.csv` | Download all archived observations as CSV |
| `GET /health` | Compatibility health route |
| `GET /climatology/demo` | Compatibility synthetic climatology route |
| `POST /analytics/summary` | Compatibility JSON summary route |

Example: analyze a local CSV with curl.

~~~bash
curl -X POST "http://127.0.0.1:8501/api/analyze/csv" \
  -H "Content-Type: text/csv" \
  --data-binary "@weather-stations.csv"
~~~

Example: request a compatibility summary from JSON.

~~~bash
curl -X POST "http://127.0.0.1:8501/analytics/summary" \
  -H "Content-Type: application/json" \
  -d '{"observations":[{"station":"STN-A","ts":"2025-01-01T00:00:00Z","temp_c":18,"precip_mm":1.2}]}'
~~~

CSV analysis returns success status, row counts, a summary object, and normalized observations. Invalid CSV or missing required fields returns HTTP 422; uploads larger than 10 MB return HTTP 413. Refer to **/docs** for the generated OpenAPI reference.

## How to read the results

- **Mean and P95:** the mean gives the average valid reading for the selected metric; P95 is the 95th percentile of that metric within the selected station view.
- **Rainfall total:** sums recorded precipitation values in the active dataset view. Missing values are not treated as measurements.
- **Daily trend:** temperature, humidity, pressure, and wind are plotted as daily means; precipitation is plotted as a daily total. The chart shows up to the latest 180 daily buckets.
- **Trend deviations:** the threshold is applied to residuals from a fitted straight-line trend across daily values. These signals are useful for exploratory review, but do not identify the cause of a reading.
- **Station rollup:** compares station coverage, mean temperature, and recorded rainfall. It is descriptive and does not adjust for station elevation, instruments, or local climate.
- **Archive counts:** show what is stored in `data/weather.db`, not what is currently loaded in the browser unless it has been saved.

## Privacy and limitations

- Demo data is fictional and should not be represented as measured national weather.
- Uploaded CSV contents are processed locally by the running application; this project does not send them to an external analytics service.
- SQLite persistence is explicit. The web dashboard writes data only when you save or call the ingestion endpoint; the database file is `data/weather.db`.
- The project does not currently ingest a real-time meteorological feed or run a physical weather simulation.
- Linear trends and residual flags are exploratory descriptive statistics, not forecasts, official alerts, or proof of bad sensor readings.
- The local server has no user authentication or multi-user access controls. Do not expose an unauthenticated development instance to untrusted networks.
- Validate units, station metadata, timestamp conventions, calibration, and quality-control expectations before research or operational use.

## Tests and development

Install the development tools:

~~~bash
python -m pip install -r requirements-dev.txt
~~~

Run the local checks:

~~~bash
ruff check src run.py tests
node --check web/app.js
bandit -q -r src run.py -ll
pip-audit -r requirements.txt --progress-spinner off
pytest -q
~~~

The GitHub Actions workflow runs Ruff, JavaScript syntax validation, Bandit, dependency auditing, and pytest on pushes and pull requests.

## Project map

~~~text
web/
  index.html                    Workspace markup and page layouts
  styles.css                    Responsive Weather Atlas theme
  app.js                        Page routing, charts, import/export, state
  assets/
    weather-atlas-logo.svg      Product mark and favicon
src/
  api.py                        FastAPI static assets and data endpoints
  weather.py                    CSV cleaning, aggregation, SQLite, pipeline
  weather_features.py           Climatology, trend analysis, compatibility API
scripts/
  generate_demo_data.py         Generate local demo data
tests/
  test_weather.py               Data pipeline tests
  test_weather_features.py      Analytics and feature tests
  test_weather_api.py            API, CSV, and archive tests
  test_ui_smoke.py               Frontend entry point and asset smoke tests
~~~

## License

MIT. See [LICENSE](LICENSE).
