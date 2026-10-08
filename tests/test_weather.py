from pathlib import Path
from src.weather import generate_sample, ingest, aggregate, anomalies
def test_pipeline(tmp_path):
    df = generate_sample(100)
    db = tmp_path / "w.db"
    assert ingest(df, db) == 100
    agg = aggregate(db)
    assert not agg.empty
    _ = anomalies(db, z=2.5)
