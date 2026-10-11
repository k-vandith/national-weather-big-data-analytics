/* Weather Atlas: dependency-free browser dashboard. */
"use strict";

const METRICS = {
  temp_c: { label: "Air temperature", short: "Temperature", unit: "°C", digits: 2 },
  humidity: { label: "Relative humidity", short: "Humidity", unit: "%", digits: 1 },
  pressure_hpa: { label: "Pressure", short: "Pressure", unit: "hPa", digits: 1 },
  wind_ms: { label: "Wind speed", short: "Wind speed", unit: "m/s", digits: 2 },
  precip_mm: { label: "Precipitation", short: "Precipitation", unit: "mm", digits: 2 },
};
const state = {
  rows: [],
  source: "synthetic-network",
  sourceLabel: "Synthetic station network",
  rowsRead: null,
  rowsRemoved: 0,
  sigma: 2,
  busy: false,
  database: { row_count: 0, station_count: 0, anomaly_count: 0 },
};

const byId = (id) => document.getElementById(id);
const num = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
};
const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[ch]));
const pretty = (value, digits = 1) => value === null || value === undefined || !Number.isFinite(Number(value))
  ? "—"
  : Number(value).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: 0 });
const dateOnly = (value) => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Unknown date" : parsed.toISOString().slice(0, 10);
};
const formatDateTime = (value) => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown time";
  return parsed.toISOString().replace("T", " ").slice(0, 16) + " UTC";
};
const safeDownload = (name, content, mime) => {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

function toast(message, type = "ok") {
  const node = byId("toast");
  node.textContent = message;
  node.classList.toggle("error", type === "error");
  node.classList.add("show");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => node.classList.remove("show"), 4200);
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, { cache: "no-store", ...options });
  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok) {
    const detail = payload.detail || payload.message || `Request failed (HTTP ${response.status})`;
    throw new Error(detail);
  }
  return payload;
}

function setBusy(isBusy, message = "") {
  state.busy = isBusy;
  byId("load-sample").disabled = isBusy;
  byId("analyze-csv").disabled = isBusy || !byId("csv-file").files?.[0];
  byId("save-database").disabled = isBusy || state.rows.length === 0;
  byId("refresh-database").disabled = isBusy;
  byId("export-csv").disabled = isBusy || state.rows.length === 0;
  byId("source-badge").textContent = message || (isBusy ? "Working…" : (state.source === "uploaded-csv" ? "Uploaded CSV" : "Demo source"));
  document.body.classList.toggle("is-busy", isBusy);
}

function selectedRows() {
  const station = byId("station-select").value || "*";
  return station === "*" ? state.rows : state.rows.filter((row) => row.station === station);
}

function selectedMetric() {
  return byId("metric-select").value in METRICS ? byId("metric-select").value : "temp_c";
}

function finiteValues(rows, metric) {
  return rows.map((row) => num(row[metric])).filter((value) => value !== null);
}

function quantile(values, q) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const position = (sorted.length - 1) * q;
  const low = Math.floor(position);
  const high = Math.ceil(position);
  return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

function average(values) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

function sum(values) {
  return values.length ? values.reduce((total, value) => total + value, 0) : null;
}

function setDataset(payload) {
  state.rows = Array.isArray(payload.observations) ? payload.observations : [];
  state.source = payload.source || "unknown";
  state.sourceLabel = state.source === "uploaded-csv"
    ? "Uploaded station CSV"
    : state.source === "synthetic-network" ? "Synthetic station network" : state.source;
  state.rowsRead = payload.rows_read ?? state.rows.length;
  state.rowsRemoved = payload.rows_removed ?? 0;
  const selector = byId("station-select");
  const previous = selector.value || "*";
  const stationNames = [...new Set(state.rows.map((row) => String(row.station || "")).filter(Boolean))].sort();
  selector.innerHTML = '<option value="*">All stations</option>' + stationNames.map((station) =>
    `<option value="${escapeHTML(station)}">${escapeHTML(station)}</option>`
  ).join("");
  selector.value = stationNames.includes(previous) ? previous : "*";

  byId("dataset-title").textContent = state.sourceLabel;
  byId("dataset-subtitle").textContent = state.source === "uploaded-csv"
    ? `${pretty(state.rowsRemoved, 0)} rows excluded during cleaning · local processing only`
    : "Reproducible synthetic observations · no live weather feed";
  byId("import-source-title").textContent = state.sourceLabel;
  byId("import-source-meta").textContent = `${pretty(state.rows.length, 0)} valid rows · ${pretty(state.rowsRemoved, 0)} excluded during cleaning · ${new Set(state.rows.map((row) => row.station)).size} station(s)`;
  renderDashboard();
  setBusy(false);
}

async function loadSample() {
  if (state.busy) return;
  const rows = Number(byId("demo-rows").value);
  setBusy(true, "Loading demo…");
  toast("Loading the local demo dataset…");
  try {
    const payload = await fetchJSON(`/api/sample?rows=${encodeURIComponent(rows)}`);
    setDataset(payload);
    toast(`Loaded ${pretty(payload.count, 0)} synthetic observations.`);
  } catch (error) {
    toast(error.message || "Unable to load demo data.", "error");
  } finally {
    setBusy(false);
  }
}

async function analyzeCSV() {
  if (state.busy) return;
  const file = byId("csv-file").files?.[0];
  if (!file) {
    toast("Choose a CSV file first.", "error");
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    toast("CSV files must be 10 MB or smaller.", "error");
    return;
  }
  setBusy(true, "Analyzing CSV…");
  byId("dataset-title").textContent = `Reading ${file.name}`;
  try {
    const bytes = await file.arrayBuffer();
    const payload = await fetchJSON("/api/analyze/csv", {
      method: "POST",
      headers: { "Content-Type": "text/csv" },
      body: bytes,
    });
    setDataset(payload);
    toast(`Analyzed ${pretty(payload.count, 0)} rows from ${file.name}.`);
  } catch (error) {
    toast(error.message || "CSV analysis failed.", "error");
    byId("dataset-title").textContent = "CSV analysis failed";
  } finally {
    setBusy(false);
  }
}

function summarize(rows, metric) {
  const values = finiteValues(rows, metric);
  const temps = finiteValues(rows, "temp_c");
  const rain = finiteValues(rows, "precip_mm");
  const dates = rows.map((row) => dateOnly(row.ts)).filter((date) => date !== "Unknown date").sort();
  return {
    count: values.length,
    mean: average(values),
    min: values.length ? Math.min(...values) : null,
    max: values.length ? Math.max(...values) : null,
    p95: quantile(values, 0.95),
    temperatureMean: average(temps),
    rainfallTotal: sum(rain),
    stationCount: new Set(rows.map((row) => row.station).filter(Boolean)).size,
    start: dates[0] || null,
    end: dates[dates.length - 1] || null,
  };
}

function dailySeries(rows, metric) {
  const buckets = new Map();
  rows.forEach((row) => {
    const value = num(row[metric]);
    const date = dateOnly(row.ts);
    if (value === null || date === "Unknown date") return;
    if (!buckets.has(date)) buckets.set(date, []);
    buckets.get(date).push(value);
  });
  let daily = [...buckets.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([date, values]) => ({
    date,
    value: metric === "precip_mm" ? sum(values) : average(values),
  }));
  // Keep SVG rendering fast on long historical archives while maintaining recent context.
  if (daily.length > 180) daily = daily.slice(-180);
  if (daily.length === 0) return [];
  const y = daily.map((item) => item.value);
  const xMean = (daily.length - 1) / 2;
  const yMean = average(y) ?? 0;
  let numerator = 0;
  let denominator = 0;
  y.forEach((value, index) => {
    numerator += (index - xMean) * (value - yMean);
    denominator += (index - xMean) ** 2;
  });
  const slope = denominator > 0 ? numerator / denominator : 0;
  const intercept = yMean - slope * xMean;
  const residuals = y.map((value, index) => value - (slope * index + intercept));
  const residualMean = average(residuals) ?? 0;
  const deviation = Math.sqrt(average(residuals.map((value) => (value - residualMean) ** 2)) || 0);
  return daily.map((item, index) => {
    const z = deviation > 1e-10 ? residuals[index] / deviation : 0;
    return {
      ...item,
      trend: slope * index + intercept,
      zscore: z,
      anomaly: deviation > 1e-10 && Math.abs(z) >= state.sigma,
    };
  });
}

function chartSVG(points, metric) {
  if (!points.length) return '<div class="empty-state">No valid data for this metric and station selection.</div>';
  const width = 880;
  const height = 290;
  const pad = { left: 56, right: 20, top: 20, bottom: 34 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const values = points.flatMap((point) => [point.value, point.trend]);
  let low = Math.min(...values);
  let high = Math.max(...values);
  if (!Number.isFinite(low) || !Number.isFinite(high)) return '<div class="empty-state">No valid numeric observations.</div>';
  if (high - low < 1e-9) { low -= 1; high += 1; }
  const spread = high - low;
  low -= spread * 0.08;
  high += spread * 0.08;
  const x = (index) => pad.left + (points.length <= 1 ? plotW / 2 : index / (points.length - 1) * plotW);
  const y = (value) => pad.top + (high - value) / (high - low) * plotH;
  const observedPath = points.map((point, index) => `${index ? "L" : "M"}${x(index).toFixed(2)},${y(point.value).toFixed(2)}`).join(" ");
  const trendPath = points.map((point, index) => `${index ? "L" : "M"}${x(index).toFixed(2)},${y(point.trend).toFixed(2)}`).join(" ");
  const fillPath = `${observedPath} L${x(points.length - 1).toFixed(2)},${(pad.top + plotH).toFixed(2)} L${pad.left},${(pad.top + plotH).toFixed(2)} Z`;
  const grid = Array.from({ length: 5 }, (_, i) => {
    const value = high - (high - low) * i / 4;
    const yy = y(value);
    return `<line class="chart-grid" x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}"/><text class="chart-axis-label" text-anchor="end" x="${pad.left - 10}" y="${yy + 4}">${escapeHTML(pretty(value, 1))}</text>`;
  }).join("");
  const dots = points.filter((point) => point.anomaly).map((point) => {
    const index = points.indexOf(point);
    return `<circle class="chart-point anomaly" cx="${x(index)}" cy="${y(point.value)}" r="4.2"><title>${escapeHTML(point.date)} · ${escapeHTML(pretty(point.value, 2))} · trend deviation</title></circle>`;
  }).join("");
  const start = escapeHTML(points[0].date);
  const end = escapeHTML(points[points.length - 1].date);
  const mid = escapeHTML(points[Math.floor((points.length - 1) / 2)].date);
  const unit = escapeHTML(METRICS[metric].unit);
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHTML(METRICS[metric].label)} from ${start} to ${end}">
    <defs><linearGradient id="plot-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#79e3d3" stop-opacity=".20"/><stop offset="100%" stop-color="#79e3d3" stop-opacity="0"/></linearGradient></defs>
    ${grid}
    <text class="chart-axis-label" x="${pad.left}" y="12">${unit}</text>
    <path class="chart-range-fill" d="${fillPath}"/>
    <path class="chart-trend-line" d="${trendPath}"/>
    <path class="chart-observed-line" d="${observedPath}"/>
    ${dots}
    <text class="chart-axis-label" x="${pad.left}" y="${height - 8}">${start}</text>
    <text class="chart-axis-label" text-anchor="middle" x="${width / 2}" y="${height - 8}">${mid}</text>
    <text class="chart-axis-label" text-anchor="end" x="${width - pad.right}" y="${height - 8}">${end}</text>
  </svg>`;
}

function stationRollup(rows) {
  const groups = new Map();
  for (const row of rows) {
    if (!row.station) continue;
    if (!groups.has(row.station)) groups.set(row.station, { station: row.station, rows: 0, temps: [], rains: [] });
    const group = groups.get(row.station);
    group.rows += 1;
    const temp = num(row.temp_c);
    const rain = num(row.precip_mm);
    if (temp !== null) group.temps.push(temp);
    if (rain !== null) group.rains.push(rain);
  }
  return [...groups.values()].map((group) => ({
    ...group,
    tempMean: average(group.temps),
    rainTotal: sum(group.rains),
  })).sort((a, b) => a.station.localeCompare(b.station));
}

function renderStationTable(rows) {
  const all = stationRollup(rows);
  const shown = all.slice(0, 18);
  byId("station-table").innerHTML = shown.length ? shown.map((station) => {
    const barWidth = station.tempMean === null ? 0 : Math.max(4, Math.min(100, (station.tempMean + 10) / 60 * 100));
    return `<tr>
      <td><span class="station-name">${escapeHTML(station.station)}</span><span class="station-sub">${pretty(station.rows, 0)} records</span></td>
      <td><span class="station-temp"><span>${pretty(station.tempMean, 1)}°</span><span class="temp-bar"><i style="width:${barWidth}%"></i></span></span></td>
      <td class="value-accent">${station.rainTotal === null ? "—" : pretty(station.rainTotal, 1) + " mm"}</td>
    </tr>`;
  }).join("") : '<tr><td colspan="3">No station observations available.</td></tr>';
  byId("station-table-foot").textContent = all.length > shown.length
    ? `Showing ${shown.length} of ${all.length} stations`
    : `${all.length} station(s) in the selected view`;
  return all;
}

function renderRecentTable(rows) {
  const recent = [...rows].sort((a, b) => String(b.ts).localeCompare(String(a.ts))).slice(0, 12);
  byId("recent-table").innerHTML = recent.length ? recent.map((row) => `<tr>
    <td><span class="station-name">${escapeHTML(row.station)}</span><span class="station-sub">${escapeHTML(formatDateTime(row.ts))}</span></td>
    <td>${num(row.temp_c) === null ? "—" : pretty(num(row.temp_c), 1) + "°"}</td>
    <td class="value-accent">${num(row.precip_mm) === null ? "—" : pretty(num(row.precip_mm), 2)}</td>
  </tr>`).join("") : '<tr><td colspan="3">No recent observations.</td></tr>';
  byId("recent-table-foot").textContent = `Showing ${recent.length} newest record(s)`;
}

function renderAnomalies(points, metric) {
  const found = points.filter((point) => point.anomaly).sort((a, b) => Math.abs(b.zscore) - Math.abs(a.zscore));
  const unit = METRICS[metric].unit;
  byId("anomaly-chip").textContent = found.length ? `${found.length} flagged` : "No deviations";
  byId("anomaly-chip").classList.toggle("warning", found.length > 0 && found.length < 5);
  byId("anomaly-chip").classList.toggle("danger", found.length >= 5);
  byId("anomaly-table").innerHTML = found.length ? found.slice(0, 10).map((point) => `<tr>
    <td>${escapeHTML(point.date)}</td><td class="value-accent">${pretty(point.value, 2)} ${escapeHTML(unit)}</td>
    <td>${pretty(point.trend, 2)} ${escapeHTML(unit)}</td><td>${pretty(point.zscore, 2)}σ</td>
  </tr>`).join("") : '<tr class="empty-review-row"><td colspan="4"><div class="quality-empty"><span class="quality-empty-icon" aria-hidden="true">✓</span><div><strong>No deviations</strong><p>No daily point crosses the configured residual threshold.</p></div></div></td></tr>';
  byId("anomaly-table-foot").textContent = found.length > 10
    ? `Showing 10 of ${found.length} daily deviations`
    : `${found.length} daily deviation(s) · this is not a forecast alert`;
}
function renderDashboard() {
  if (!state.rows.length) return;
  const rows = selectedRows();
  const metric = selectedMetric();
  const settings = METRICS[metric];
  const stats = summarize(rows, metric);
  const points = dailySeries(rows, metric);
  const rainTotal = sum(finiteValues(rows, "precip_mm"));
  const stations = new Set(rows.map((row) => row.station).filter(Boolean)).size;

  byId("observations-count").textContent = pretty(rows.length, 0);
  byId("stations-count").textContent = pretty(stations, 0);
  byId("period-label").textContent = stats.start && stats.end ? `${stats.start} — ${stats.end}` : "No time span";
  byId("kpi-mean").textContent = stats.mean === null ? "—" : `${pretty(stats.mean, settings.digits)} ${settings.unit}`;
  byId("kpi-mean-foot").textContent = `Average ${settings.label.toLowerCase()} for selected records`;
  byId("kpi-p95").textContent = stats.p95 === null ? "—" : `${pretty(stats.p95, settings.digits)} ${settings.unit}`;
  byId("kpi-range").textContent = stats.min === null ? "Range —" : `Range ${pretty(stats.min, settings.digits)} to ${pretty(stats.max, settings.digits)} ${settings.unit}`;
  byId("kpi-count").textContent = `${pretty(stats.count, 0)} valid values`;
  byId("kpi-anomalies").textContent = pretty(points.filter((point) => point.anomaly).length, 0);
  byId("sigma-caption").textContent = `${state.sigma.toFixed(2)}σ threshold`;
  byId("kpi-rain").textContent = rainTotal === null ? "—" : `${pretty(rainTotal, 1)} mm`;
  byId("chart-title").textContent = `${settings.short} trend`;
  byId("chart-subtitle").textContent = metric === "precip_mm"
    ? "Daily total and fitted linear trend"
    : "Daily mean and fitted linear trend";
  byId("chart-range").textContent = points.length
    ? `${points.length} daily bucket(s) · ${points[0].date} to ${points[points.length - 1].date}`
    : "No chart data";
  byId("chart-canvas").innerHTML = chartSVG(points, metric);
  renderStationTable(rows);
  renderRecentTable(rows);
  renderAnomalies(points, metric);
  byId("source-badge").textContent = state.source === "uploaded-csv" ? "Uploaded CSV" : "Demo source";
  byId("save-database").disabled = state.busy || !state.rows.length;
  byId("export-csv").disabled = state.busy || !state.rows.length;
}

function csvCell(value, stringColumn = false) {
  let content = value === null || value === undefined ? "" : String(value);
  const trimmed = content.replace(/^[ \\t\\r\\n]+/, "");
  if (stringColumn && (/^[\\t\\r\\n]/.test(content) || /^[=+@\\-]/.test(trimmed))) content = "'" + content;
  return '"' + content.replace(/"/g, '""') + '"';
}

function toCSV(rows) {
  const columns = ["station", "ts", "temp_c", "humidity", "pressure_hpa", "wind_ms", "precip_mm"];
  return [columns.map((column) => csvCell(column, true)).join(",")]
    .concat(rows.map((row) => columns.map((column) => csvCell(row[column], column === "station" || column === "ts")).join(",")))
    .join("\r\n") + "\r\n";
}

function exportCurrentCSV() {
  const rows = selectedRows();
  if (!rows.length) {
    toast("There are no records to export.", "error");
    return;
  }
  safeDownload("weather-observations-clean.csv", toCSV(rows), "text/csv;charset=utf-8");
  toast(`Exported ${pretty(rows.length, 0)} cleaned observations.`);
}

function exportReport() {
  const rows = selectedRows();
  if (!rows.length) {
    toast("There are no records to report.", "error");
    return;
  }
  const metric = selectedMetric();
  const stats = summarize(rows, metric);
  const points = dailySeries(rows, metric);
  const report = {
    generated_at_utc: new Date().toISOString(),
    source: state.sourceLabel,
    rows_read: state.rowsRead,
    rows_removed: state.rowsRemoved,
    selected_station: byId("station-select").value || "*",
    metric,
    unit: METRICS[metric].unit,
    anomaly_threshold_sigma: state.sigma,
    observation_count: rows.length,
    station_count: stats.stationCount,
    period_start: stats.start,
    period_end: stats.end,
    statistics: stats,
    daily_deviations: points.filter((point) => point.anomaly),
    limitations: [
      "Demo observations are synthetic, not live meteorological measurements.",
      "Trend deviations are descriptive statistics, not forecasts or official alerts.",
      "Station coverage and measurement quality depend on the uploaded file.",
    ],
  };
  safeDownload("weather-analytics-report.json", JSON.stringify(report, null, 2), "application/json");
  toast("Analytics JSON report exported.");
}

async function refreshDatabase() {
  try {
    const payload = await fetchJSON("/api/stored/summary");
    state.database = payload;
    byId("database-rows").textContent = pretty(payload.row_count, 0);
    byId("database-stations").textContent = pretty(payload.station_count, 0);
    byId("database-anomalies").textContent = pretty(payload.anomaly_count, 0);
    byId("database-status").textContent = payload.row_count
      ? "Project-local SQLite archive is available. Saving merges by station and timestamp."
      : "Archive is ready. Save the current dataset to create your local station history.";
  } catch (error) {
    byId("database-status").textContent = error.message || "Unable to query the local archive.";
  }
}

async function saveDatabase() {
  if (state.busy || !state.rows.length) return;
  setBusy(true, "Saving to SQLite…");
  try {
    const payload = await fetchJSON("/api/ingest/csv", {
      method: "POST",
      headers: { "Content-Type": "text/csv" },
      body: toCSV(state.rows),
    });
    await refreshDatabase();
    toast(`Saved ${pretty(payload.rows_upserted, 0)} observation(s). Archive now contains ${pretty(payload.database_rows, 0)} rows across ${pretty(payload.database_stations, 0)} stations.`);
  } catch (error) {
    toast(error.message || "Unable to save observations.", "error");
  } finally {
    setBusy(false);
    renderDashboard();
  }
}


const PAGE_CONFIG = {
  "/": { key: "overview", title: "Weather overview", description: "Summary of the active weather analytics dataset." },
  "/import": { key: "import", title: "Import data", description: "Generate demo observations or validate and analyze an uploaded station CSV." },
  "/network": { key: "network", title: "Station network", description: "Compare station coverage and inspect recent readings." },
  "/quality": { key: "quality", title: "Quality review", description: "Review descriptive daily residuals against a simple linear trend." },
  "/archive": { key: "archive", title: "Local archive", description: "Save, inspect, and export observations from the project-local SQLite archive." },
};

function activatePage() {
  const pathname = window.location.pathname.replace(/\/+$/, "") || "/";
  const page = PAGE_CONFIG[pathname] || PAGE_CONFIG["/"];
  document.body.dataset.page = page.key;
  document.querySelectorAll("[data-view]").forEach((view) => {
    view.hidden = view.dataset.view !== page.key;
  });
  document.querySelectorAll("[data-page-link]").forEach((link) => {
    const active = link.dataset.pageLink === page.key;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  byId("page-title").textContent = page.title;
  byId("page-description").textContent = page.description;
  document.title = `${page.title} | Weather Atlas`;
}

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-route-link]");
  if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const destination = new URL(link.href, window.location.href);
  if (destination.origin !== window.location.origin || !Object.prototype.hasOwnProperty.call(PAGE_CONFIG, destination.pathname)) return;
  event.preventDefault();
  if (destination.pathname !== window.location.pathname) history.pushState({}, "", destination.pathname);
  activatePage();
  renderDashboard();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

window.addEventListener("popstate", () => {
  activatePage();
  renderDashboard();
});

async function boot() {
  byId("demo-rows-out").textContent = Number(byId("demo-rows").value).toLocaleString();
  byId("sigma-out").textContent = `${Number(byId("sigma-select").value).toFixed(2)}σ`;
  try {
    await fetchJSON("/api/health");
    byId("api-status").textContent = "API connected";
  } catch {
    byId("api-status").textContent = "API unavailable";
    toast("The local API is not reachable. Start the app with python run.py.", "error");
    return;
  }
  await loadSample();
  await refreshDatabase();
}

byId("load-sample").addEventListener("click", loadSample);
byId("demo-rows").addEventListener("input", (event) => {
  byId("demo-rows-out").textContent = Number(event.target.value).toLocaleString();
});
byId("demo-rows").addEventListener("change", () => {
  if (state.source === "synthetic-network") loadSample();
});
byId("station-select").addEventListener("change", renderDashboard);
byId("metric-select").addEventListener("change", renderDashboard);
byId("sigma-select").addEventListener("input", (event) => {
  state.sigma = Number(event.target.value);
  byId("sigma-out").textContent = `${state.sigma.toFixed(2)}σ`;
  renderDashboard();
});
byId("csv-file").addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  byId("file-name").textContent = file ? `${file.name} · ${pretty(file.size / 1024, 1)} KB` : "Drop a file here or browse";
  byId("analyze-csv").disabled = !file || state.busy;
});
byId("analyze-csv").addEventListener("click", analyzeCSV);
byId("export-csv").addEventListener("click", exportCurrentCSV);
byId("export-report-top").addEventListener("click", exportReport);
byId("save-database").addEventListener("click", saveDatabase);
byId("refresh-database").addEventListener("click", refreshDatabase);
byId("export-database").addEventListener("click", () => { window.location.href = "/api/stored.csv"; });

const drop = byId("file-drop");
["dragenter", "dragover"].forEach((eventName) => drop.addEventListener(eventName, (event) => {
  event.preventDefault();
  drop.classList.add("dragover");
}));
["dragleave", "drop"].forEach((eventName) => drop.addEventListener(eventName, (event) => {
  event.preventDefault();
  drop.classList.remove("dragover");
}));
drop.addEventListener("drop", (event) => {
  const file = event.dataTransfer?.files?.[0];
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".csv")) {
    toast("Choose a .csv file.", "error");
    return;
  }
  const transfer = new DataTransfer();
  transfer.items.add(file);
  byId("csv-file").files = transfer.files;
  byId("csv-file").dispatchEvent(new Event("change", { bubbles: true }));
  analyzeCSV();
});

activatePage();
boot();
