"""Optional FastAPI entry point.

Run from the repository root with:
    uvicorn src.api:app --reload
"""
from src.weather_features import create_fastapi_app

app = create_fastapi_app()
