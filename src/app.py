"""Weather analytics workspace."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import plotly.graph_objects as go
import streamlit as st
from src.ui_theme import theme_css
from src.weather import generate_sample
from src.weather_features import benchmark_engines, climatology_stats, trend_and_anomalies

@st.cache_data
def _frame(n: int):
    df = generate_sample(n=n, seed=3)
    return df

def main() -> None:
    st.set_page_config(page_title="Weather analytics", layout="wide")
    st.markdown(theme_css("#7eb6ff"), unsafe_allow_html=True)
    st.markdown('<div class="top"><div><div class="kicker">Climate analytics</div><p class="title">National weather data</p></div><div class="pill">Pandas · optional DuckDB/Polars</div></div>', unsafe_allow_html=True)
    n = st.sidebar.slider("Rows", 200, 5000, 800, 100)
    df = _frame(n)
    col = "temp_c" if "temp_c" in df.columns else df.select_dtypes("number").columns[0]
    stats = climatology_stats(df, col)
    tr = trend_and_anomalies(df, col)
    st.markdown(f'<div class="panel"><div class="kicker">{col}</div><p class="title">{stats["mean"]:.1f} mean</p><p class="muted">min {stats["min"]:.1f} · max {stats["max"]:.1f} · p95 {stats["p95"]:.1f} · {int(tr["is_anomaly"].sum())} anomalies</p></div>', unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=tr[col], name="Observed", line=dict(color="#7eb6ff")))
    fig.add_trace(go.Scatter(y=tr["trend"], name="Trend", line=dict(color="#e0b15a")))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#e7ecf3", height=360, title="Series and linear trend")
    st.plotly_chart(fig, width="stretch")
    if st.button("Run engine benchmark"):
        out = ROOT / "data" / "bench.csv"
        result = benchmark_engines(df, out)
        st.json(result)
        st.caption("Negative times mean that engine is not installed. Core analytics still use pandas.")

if __name__ == "__main__":
    main()
