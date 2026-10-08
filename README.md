# National Weather Big Data Analytics Platform

Local-first weather analytics: ingestion → validation → SQLite storage → aggregation → anomaly detection → API-ready.

Storage layer is SQLite today; schema is portable to PostgreSQL.

## Installation

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Demo
```bash
python scripts/generate_demo_data.py
pytest -v
```

## License
MIT
