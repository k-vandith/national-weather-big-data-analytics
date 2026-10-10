"""National weather analytics dashboard with CSV ingestion and station rollups."""
from __future__ import annotations

import json
import sys
from html import escape
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.ui_theme import theme_css
from src.weather import (
    generate_sample,
    load_weather_csv,
    normalize_observations,
    summarize_observations,
)
from src.weather_features import benchmark_engines, climatology_stats, trend_and_anomalies


METRICS = {
    "Air temperature": ("temp_c", "°C"),
    "Relative humidity": ("humidity", "%"),
    "Pressure": ("pressure_hpa", "hPa"),
    "Wind speed": ("wind_ms", "m/s"),
    "Precipitation": ("precip_mm", "mm"),
}


@st.cache_data
def _sample(n: int) -> pd.DataFrame:
    return generate_sample(n=n, seed=3)


def _sample_csv() -> bytes:
    return _sample(48).to_csv(index=False).encode("utf-8")


def _station_rollup(frame: pd.DataFrame) -> pd.DataFrame:
    rollup = (
        frame.groupby("station", as_index=False)
        .agg(
            observations=("station", "size"),
            mean_temp_c=("temp_c", "mean"),
            mean_humidity=("humidity", "mean"),
            total_precip_mm=("precip_mm", "sum"),
            mean_wind_ms=("wind_ms", "mean"),
        )
        .sort_values("station")
    )
    return rollup


def main() -> None:
    st.set_page_config(
        page_title="National Weather Analytics",
        page_icon="🌐",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(theme_css("#6ee7d8", danger="#fb7185", ok="#34d399", warn="#fbbf24"), unsafe_allow_html=True)
    st.markdown(
        """
        <div class="top">
          <div>
            <div class="kicker">Atmospheric intelligence · Data operations</div>
            <p class="title">National weather analytics</p>
            <p class="muted">Station observations, climatology signals, and regional rollups in one workspace.</p>
          </div>
          <div class="pill">ETL / ANALYTICS CONSOLE</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("### Dataset")
        mode = st.radio(
            "Data source",
            ["Synthetic network", "Upload station CSV"],
            help="The synthetic network works offline. Uploaded data stays in this local app session.",
        )
        sample_rows = st.slider("Synthetic observation rows", min_value=200, max_value=5000, value=1200, step=200)
        st.download_button(
            "Download CSV template",
            data=_sample_csv(),
            file_name="weather-stations-template.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.divider()
        st.markdown("### Analysis")
        anomaly_sigma = st.slider(
            "Trend anomaly threshold (σ)",
            min_value=1.0,
            max_value=4.0,
            value=2.0,
            step=0.25,
        )

    preview_only = False
    rows_read: int | None = None
    upload = None
    if mode == "Upload station CSV":
        upload = st.file_uploader(
            "Load station observations",
            type=["csv"],
            help=(
                "Required fields: station, timestamp/date, and temperature in °C. Common aliases such as "
                "station_id, datetime, temperature_c, rainfall_mm and wind_speed_ms are supported. "
                "Maximum 10 MB and 100,000 rows."
            ),
        )
        if upload is None:
            preview_only = True
            st.info("Upload a station CSV to analyse your own observations. Sample data is shown as a preview meanwhile.")
            frame = _sample(sample_rows)
            source_label = "Synthetic preview · no upload selected"
        else:
            try:
                raw = load_weather_csv(upload.getvalue())
                rows_read = len(raw)
                frame = normalize_observations(raw)
                source_label = f"Uploaded CSV · {escape(upload.name)}"
                if frame.empty:
                    st.error("No valid observations remain. Check station, timestamp, and temperature values.")
                    st.stop()
                removed = rows_read - len(frame)
                if removed:
                    st.warning(
                        f"Cleaning kept {len(frame):,} of {rows_read:,} rows "
                        f"({removed:,} removed for invalid required values or duplicate station/timestamps)."
                    )
            except (ValueError, TypeError, UnicodeDecodeError, pd.errors.ParserError) as exc:
                st.error(f"Could not load this CSV: {exc}")
                st.stop()
    else:
        frame = _sample(sample_rows)
        source_label = "Synthetic station network"

    frame = normalize_observations(frame)
    if frame.empty:
        st.error("No usable observations available for analysis.")
        st.stop()

    frame["ts_dt"] = pd.to_datetime(frame["ts"], errors="coerce", utc=True, format="mixed")
    frame = frame.dropna(subset=["ts_dt"]).sort_values(["ts_dt", "station"]).reset_index(drop=True)
    if frame.empty:
        st.error("No valid timestamps remain after parsing.")
        st.stop()

    all_stations = sorted(frame["station"].unique().tolist())
    c1, c2 = st.columns([1, 1])
    with c1:
        station_focus = st.selectbox("Station focus", ["All stations", *all_stations])
    available_metrics = [
        label for label, (column, _) in METRICS.items()
        if column in frame.columns and frame[column].notna().any()
    ]
    with c2:
        metric_label = st.selectbox("Metric", available_metrics, index=0)
    metric, unit = METRICS[metric_label]

    filtered = frame if station_focus == "All stations" else frame[frame["station"] == station_focus]
    filtered = filtered.copy()
    if filtered.empty:
        st.error("No records match the selected station.")
        st.stop()

    try:
        summary = summarize_observations(filtered)
        stats = climatology_stats(filtered, metric)
        tr = trend_and_anomalies(filtered, metric, anomaly_sigma=anomaly_sigma)
    except (ValueError, TypeError, KeyError) as exc:
        st.error(f"Unable to calculate analytics: {exc}")
        st.stop()

    st.markdown(
        f"""
        <div class="dataset-bar">
          <span class="source-dot"></span>
          <span>{source_label}</span>
          <span class="dataset-sep">/</span>
          <span>{len(filtered):,} observations</span>
          <span class="dataset-sep">/</span>
          <span>{summary['station_count']} station(s)</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    anomaly_count = int(tr["is_anomaly"].sum())
    precipitation_total = pd.to_numeric(filtered["precip_mm"], errors="coerce").sum(min_count=1)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Mean {metric_label.lower()}", f"{stats['mean']:.2f} {unit}")
    c2.metric("P95", f"{stats['p95']:.2f} {unit}")
    c3.metric("Trend deviations", f"{anomaly_count:,}", help="Residuals from a linear trend exceed the selected threshold.")
    c4.metric("Reported precipitation", "—" if pd.isna(precipitation_total) else f"{precipitation_total:.1f} mm")

    # Daily aggregation makes the time plot comparable even for multi-station uploads.
    timed = filtered.set_index("ts_dt")[metric].sort_index()
    daily = timed.resample("D").sum(min_count=1) if metric == "precip_mm" else timed.resample("D").mean()
    daily = daily.dropna()
    daily_frame = pd.DataFrame({"day": daily.index, metric: daily.to_numpy(dtype=float)}).reset_index(drop=True)
    try:
        daily_trend = trend_and_anomalies(daily_frame.rename(columns={"day": "ts"}), metric, anomaly_sigma=anomaly_sigma)
    except ValueError:
        daily_trend = daily_frame.copy()
        daily_trend["trend"] = daily_trend[metric]
        daily_trend["is_anomaly"] = False

    chart_col, rollup_col = st.columns([1.5, 1])
    with chart_col:
        chart = go.Figure()
        chart.add_trace(go.Scatter(
            x=daily_trend["ts"],
            y=daily_trend[metric],
            mode="lines+markers",
            name="Daily observed",
            line={"color": "#6ee7d8", "width": 2.2},
            marker={"size": 5},
            fill="tozeroy" if metric == "precip_mm" else None,
            fillcolor="rgba(110,231,216,0.10)" if metric == "precip_mm" else None,
        ))
        chart.add_trace(go.Scatter(
            x=daily_trend["ts"],
            y=daily_trend["trend"],
            mode="lines",
            name="Linear trend",
            line={"color": "#fbbf24", "width": 1.8, "dash": "dash"},
        ))
        anomalous = daily_trend[daily_trend.get("is_anomaly", False)]
        if not anomalous.empty:
            chart.add_trace(go.Scatter(
                x=anomalous["ts"], y=anomalous[metric], mode="markers",
                name="Trend deviation", marker={"color": "#fb7185", "size": 10, "symbol": "diamond"},
            ))
        chart.update_layout(
            title=f"Daily {metric_label.lower()} · {station_focus.lower()}",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e4edf5",
            height=390,
            margin={"l": 8, "r": 8, "t": 55, "b": 8},
            legend={"orientation": "h", "y": 1.12, "x": 0},
            xaxis_title=None,
            yaxis_title=f"{metric_label} ({unit})",
        )
        st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})

    with rollup_col:
        rollup = _station_rollup(filtered)
        st.markdown('<div class="section-kicker">Station network</div>', unsafe_allow_html=True)
        st.dataframe(
            rollup,
            use_container_width=True,
            hide_index=True,
            height=340,
            column_config={
                "station": st.column_config.TextColumn("Station"),
                "observations": st.column_config.NumberColumn("Rows", format="%d"),
                "mean_temp_c": st.column_config.NumberColumn("Mean °C", format="%.2f"),
                "mean_humidity": st.column_config.NumberColumn("Mean RH", format="%.1f"),
                "total_precip_mm": st.column_config.NumberColumn("Rain mm", format="%.2f"),
                "mean_wind_ms": st.column_config.NumberColumn("Wind m/s", format="%.2f"),
            },
        )

    st.markdown("### Quality review")
    anomalies = tr[tr["is_anomaly"]].copy()
    q1, q2 = st.columns([1.2, 1])
    with q1:
        if anomalies.empty:
            st.success(f"No trend deviations exceed {anomaly_sigma:.2f}σ for {metric_label.lower()}.")
        else:
            anomalies = anomalies.assign(abs_z=anomalies["anomaly_zscore"].abs()).sort_values("abs_z", ascending=False)
            st.dataframe(
                anomalies[[c for c in ["station", "ts", metric, "trend", "anomaly_zscore"] if c in anomalies.columns]].head(30),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "anomaly_zscore": st.column_config.NumberColumn("Residual z-score", format="%.2f"),
                    "trend": st.column_config.NumberColumn("Trend", format="%.2f"),
                },
            )
    with q2:
        coverage = (
            filtered.groupby("station", as_index=False)
            .agg(
                first_seen=("ts_dt", "min"),
                last_seen=("ts_dt", "max"),
                reported_temperature=("temp_c", "count"),
                reported_rainfall=("precip_mm", "count"),
            )
        )
        st.dataframe(
            coverage,
            use_container_width=True,
            hide_index=True,
            column_config={
                "first_seen": st.column_config.DatetimeColumn("First observation", format="YYYY-MM-DD HH:mm"),
                "last_seen": st.column_config.DatetimeColumn("Last observation", format="YYYY-MM-DD HH:mm"),
                "reported_temperature": st.column_config.NumberColumn("Temp values", format="%d"),
                "reported_rainfall": st.column_config.NumberColumn("Rain values", format="%d"),
            },
        )

    st.markdown("### Export & engine benchmark")
    export_col, benchmark_col = st.columns([1, 1])
    report = {
        "source": source_label,
        "preview_only": preview_only,
        "rows_read": rows_read,
        "rows_analysed": int(len(filtered)),
        "station_focus": station_focus,
        "metric": metric,
        "unit": unit,
        "anomaly_threshold_sigma": float(anomaly_sigma),
        **summary,
    }
    with export_col:
        st.download_button(
            "Download cleaned observations",
            data=filtered.drop(columns=["ts_dt"]).to_csv(index=False).encode("utf-8"),
            file_name="weather-observations-clean.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "Download analytics report",
            data=json.dumps(report, indent=2, default=str),
            file_name="weather-analytics-report.json",
            mime="application/json",
            use_container_width=True,
        )
    with benchmark_col:
        if st.button("Benchmark available engines", use_container_width=True):
            with st.spinner("Running small local CSV/group-by benchmarks…"):
                try:
                    with tempfile.TemporaryDirectory(prefix="weather-benchmark-") as temp_dir:
                        result = benchmark_engines(filtered.drop(columns=["ts_dt"]), Path(temp_dir) / "benchmark.parquet")
                    rows = []
                    for engine in ("pandas", "polars", "duckdb"):
                        value = result.get(f"{engine}_s", -1.0)
                        rows.append({
                            "Engine": engine,
                            "Seconds": value if isinstance(value, (int, float)) and value >= 0 else None,
                            "Status": "available" if isinstance(value, (int, float)) and value >= 0 else str(result.get(f"{engine}_error", "not installed")),
                        })
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                except (ValueError, OSError, KeyError) as exc:
                    st.error(f"Benchmark could not run: {exc}")
                st.caption("Indicative timings for this filtered sample only; not a national-scale performance claim.")

    st.caption(
        "Synthetic observations are fictional. Uploaded rows are processed in this local app session; "
        "the dashboard does not contact a weather provider. Anomaly flags are descriptive signals, not forecasts."
    )


if __name__ == "__main__":
    main()
