# National Weather Big Data Analytics Platform

ETL and analytics layer for national-scale weather observations: ingest, aggregate, and visualise temperature, precipitation, and anomaly indicators.

## Problem Statement

Agencies and researchers need a reproducible pipeline to clean multi-station weather CSVs, compute regional aggregates, and serve dashboards or APIs without proprietary stacks.

## Overview

Load station time series, run cleaning and aggregation, expose Streamlit dashboards and an optional FastAPI surface for programmatic access.

## Features

- **CSV / batch ingest**
- **Cleaning & aggregation** – daily / regional rollups
- **Anomaly highlights**
- **Streamlit analytics UI**
- **Optional FastAPI endpoints**
- **Demo national-scale synthetic set**

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Streamlit  │────▶│   Weather    │────▶│  Aggregates │
│  + FastAPI  │     │   pipeline   │     │  + plots    │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────▼───────┐
                    │  Station CSV │
                    └──────────────┘
```

## Tech Stack

- Python 3.11+
- Pandas / NumPy
- Streamlit + Plotly
- FastAPI + Uvicorn
- pytest

## Repository Structure

```
national-weather-big-data-analytics/
├── README.md
├── requirements.txt
├── src/
│   └── weather.py
├── tests/
│   └── test_weather.py
├── data/
├── scripts/
│   ├── setup_env.py
│   ├── setup.sh
│   ├── setup.ps1
│   └── generate_demo_data.py
└── docs/
```

## System Requirements

| Mode | CPU | RAM | Disk | GPU |
|------|-----|-----|------|-----|
| Demo | Any | 2 GB | 1 GB | Not needed |

## Installation

### Recommended (all platforms) — automated bootstrap

Handles missing `ensurepip`, symlink restrictions, and installs dependencies into `.venv`:

```bash
git clone https://github.com/k-vandith/national-weather-big-data-analytics.git
cd national-weather-big-data-analytics
python3 scripts/setup_env.py    # or:  python scripts/setup_env.py
```

Then activate:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

### Manual setup

#### Windows (PowerShell)

```powershell
git clone https://github.com/k-vandith/national-weather-big-data-analytics.git
cd national-weather-big-data-analytics
python -m venv .venv --copies
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### Linux / macOS

```bash
git clone https://github.com/k-vandith/national-weather-big-data-analytics.git
cd national-weather-big-data-analytics
# If venv fails with ensurepip errors:
#   sudo apt install python3-venv python3-pip
python3 -m venv .venv --copies
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Why `--copies`?

Some environments cannot create symlinks inside a venv (`Operation not permitted` on `lib64 → lib`). Using `--copies` avoids that. `scripts/setup_env.py` tries `--copies` first automatically.

## Environment Variables

Optional FastAPI host/port via environment if extended.

## Dataset / Demo Mode

```bash
python scripts/generate_demo_data.py
```

## Running the Application

```bash
streamlit run src/weather.py
# Optional API:
uvicorn src.weather:app --reload   # if FastAPI app exposed
```

## API Usage

```python
from src.weather import run_pipeline
print(run_pipeline("data/demo_stations.csv"))
```

## Testing

```bash
pytest -v
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: src` | Run from project root; ensure `PYTHONPATH=.` |
| `venv` / ensurepip fails | Run `python3 scripts/setup_env.py` or install `python3-venv` |
| `Operation not permitted` on lib64 | Use `python3 -m venv .venv --copies` |
| Missing dependency | Activate `.venv` and re-run `pip install -r requirements.txt` |

## Limitations

- Demo scale is synthetic; production needs real station feeds.
- Spatial joins / GIS layers are minimal in the base release.
- Not a numerical weather prediction model.

## Security / Privacy

- Weather observations are generally non-sensitive; still protect API keys if you add external feeds.

## Future Improvements

- Parquet / DuckDB backend for larger archives
- Map overlays
- Scheduled ETL jobs

## License

MIT
