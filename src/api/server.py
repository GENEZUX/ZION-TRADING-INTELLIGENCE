from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pathlib import Path

app = FastAPI(title="ZION API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "zion.db"

@app.get("/api/metricas")
def get_metricas():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        velas = conn.execute("SELECT COUNT(*) FROM normalized_records").fetchone()[0]
        runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        cuarentena = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        return {"total_velas": velas, "total_runs": runs, "total_cuarentena": cuarentena}
    finally:
        conn.close()
