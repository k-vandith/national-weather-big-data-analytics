from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.weather import generate_sample, ingest
ROOT = Path(__file__).resolve().parents[1]
csv = ROOT / "data" / "sample" / "weather.csv"
db = ROOT / "data" / "sample" / "weather.db"
csv.parent.mkdir(parents=True, exist_ok=True)
df = generate_sample()
df.to_csv(csv, index=False)
if db.exists(): db.unlink()
print("ingested", ingest(df, db), "rows")
