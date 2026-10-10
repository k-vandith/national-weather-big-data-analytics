from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_without_browser() -> None:
    app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
    result = AppTest.from_file(str(app_path)).run(timeout=30)
    assert not result.exception
