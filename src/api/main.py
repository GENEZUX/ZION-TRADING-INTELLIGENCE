"""API backend para ZProMax - ZION Trading Intelligence.
Expone los datos reales de la base de datos SQLite (data/zion.db).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pathlib import Path

app = FastAPI(title="ZION Trading Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "zion.db"

def get_db_connection():
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/status")
def get_status():
    return {
        "sistema": "ZION Trading Intelligence",
        "base_de_datos": "conectada" if DB_PATH.exists() else "no encontrada",
        "modo": "REAL (sin simulacion)"
    }

@app.get("/api/metricas")
def get_metricas():
    conn = get_db_connection()
    if not conn:
        return {"error": "Base de datos no inicializada."}
    try:
        total_velas = conn.execute("SELECT COUNT(*) FROM normalized_records").fetchone()[0]
        total_runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        total_cuarentena = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        return {
            "total_velas": total_velas,
            "total_runs": total_runs,
            "total_cuarentena": total_cuarentena
        }
    finally:
        conn.close()
