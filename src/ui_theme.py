"""Offline visual system for the national weather analytics console."""


def theme_css(
    accent: str = "#6ee7d8",
    danger: str = "#fb7185",
    ok: str = "#34d399",
    warn: str = "#fbbf24",
) -> str:
    return f"""
<style>
:root {{
  --bg:#07121b;
  --surface:#0e202b;
  --surface-raised:#132b37;
  --text:#e4edf5;
  --muted:#91a7b6;
  --border:#23404b;
  --accent:{accent};
  --danger:{danger};
  --ok:{ok};
  --warn:{warn};
}}
html, body, .stApp {{
  background:
    radial-gradient(ellipse at 8% -5%, rgba(110,231,216,.10), transparent 34rem),
    radial-gradient(ellipse at 96% 15%, rgba(96,165,250,.08), transparent 28rem),
    var(--bg);
  color:var(--text);
  font-family:"Segoe UI", ui-sans-serif, system-ui, sans-serif;
}}
[data-testid="stHeader"] {{ background:rgba(7,18,27,.72); }}
[data-testid="stSidebar"] {{
  background:linear-gradient(180deg, #0d202b 0%, #091720 100%);
  border-right:1px solid var(--border);
}}
[data-testid="stSidebar"] > div {{ padding-top:1.2rem; }}
.block-container {{ padding-top:1.45rem; padding-bottom:2.5rem; max-width:1500px; }}
.top {{
  display:flex; justify-content:space-between; align-items:flex-end;
  gap:20px; margin-bottom:1.25rem; padding-bottom:1.25rem;
  border-bottom:1px solid var(--border);
}}
.kicker, .section-kicker {{
  color:var(--accent); text-transform:uppercase;
  letter-spacing:.16em; font-size:.68rem; font-weight:750;
}}
.title {{
  font-size:clamp(1.7rem, 3vw, 2.55rem); font-weight:760;
  letter-spacing:-.05em; line-height:1.08; margin:.4rem 0 .65rem;
}}
.muted {{ color:var(--muted); font-size:.9rem; }}
.pill {{
  border:1px solid rgba(110,231,216,.33);
  border-radius:999px; padding:7px 12px;
  background:rgba(110,231,216,.07); color:#a7f3e8;
  font-size:.68rem; font-weight:750; letter-spacing:.08em; white-space:nowrap;
}}
.dataset-bar {{
  display:flex; gap:10px; align-items:center; flex-wrap:wrap;
  border:1px solid var(--border); background:rgba(14,32,43,.72);
  border-radius:12px; padding:10px 14px; margin:.8rem 0 1rem;
  color:#c7d8e2; font-size:.8rem;
}}
.source-dot {{ height:8px; width:8px; border-radius:50%; background:var(--accent); box-shadow:0 0 12px var(--accent); }}
.dataset-sep {{ color:#466371; }}
[data-testid="stMetric"] {{
  background:linear-gradient(135deg, rgba(19,43,55,.95), rgba(14,32,43,.8));
  border:1px solid var(--border); border-radius:15px; padding:15px 16px;
}}
[data-testid="stMetricLabel"] {{ color:var(--muted); font-size:.8rem; }}
[data-testid="stMetricValue"] {{ font-weight:760; letter-spacing:-.035em; }}
[data-testid="stMetricDelta"] {{ font-size:.8rem; }}
div[data-testid="stVerticalBlock"] > div:has(> [data-testid="stPlotlyChart"]) {{
  background:rgba(14,32,43,.55); border:1px solid var(--border);
  border-radius:17px; padding:8px; margin-bottom:.7rem;
}}
[data-testid="stDataFrame"] {{ border:1px solid var(--border); border-radius:12px; overflow:hidden; }}
[data-testid="stFileUploader"] {{ border:1px dashed #3a626d; border-radius:13px; padding:8px; }}
.stButton > button, .stDownloadButton > button {{
  border-radius:10px; border:1px solid var(--border);
  transition:transform .15s ease, border-color .15s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
  border-color:var(--accent); transform:translateY(-1px);
}}
hr {{ border-color:var(--border); }}
@media (max-width: 850px) {{
  .top {{ align-items:flex-start; flex-direction:column; }}
  .pill {{ white-space:normal; }}
  .block-container {{ padding-top:1rem; }}
}}
</style>
"""


