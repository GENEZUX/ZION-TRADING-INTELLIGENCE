"""ZION Unified API - El servidor definitivo para ZProMax (Puerto 8000)."""
import sqlite3
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Intentamos importar el motor Voltex
try:
    from src.analyze.voltex import ejecutar_bucle_voltex
except ImportError:
    ejecutar_bucle_voltex = None

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "zion.db"

app = FastAPI(title="ZION Unified API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def get_db():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

# 1. RUTA PARA LA BASE LOCAL (ZProMax)
@app.get("/api/metricas")
def get_metricas():
    conn = get_db()
    try:
        velas = conn.execute("SELECT COUNT(*) FROM normalized_records").fetchone()[0]
        runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        cuarentena = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        return {
            "status": "success",
            "total_velas": velas, "candles": velas,
            "total_runs": runs, "runs": runs,
            "total_cuarentena": cuarentena, "quarantine": cuarentena,
            "counts": {"candles": velas, "runs": runs, "quarantine": cuarentena}
        }
    finally:
        conn.close()

# 2. RUTA PARA EL MERCADO GLOBAL
@app.get("/api/mercado")
def get_mercado():
    conn = get_db()
    try:
        query = """
            SELECT asset_class, instrument_id, close as precio, event_time_utc
            FROM normalized_records
            WHERE norm_id IN (SELECT MAX(norm_id) FROM normalized_records GROUP BY instrument_id)
            ORDER BY asset_class
        """
        rows = conn.execute(query).fetchall()
        return {"status": "success", "mercado": [dict(row) for row in rows]}
    finally:
        conn.close()

# 3. RUTA PARA EL BUCLE VOLTEX
@app.get("/api/voltex/{instrument_id}")
def get_voltex(instrument_id: str):
    if not ejecutar_bucle_voltex:
        return {"error": "Motor Voltex no encontrado"}
    return ejecutar_bucle_voltex(instrument_id)

# 4. RUTA PARA MI CARTERA (Datos reales basados en los precios)
@app.get("/api/cartera")
def get_cartera():
    conn = get_db()
    try:
        rows = conn.execute("SELECT instrument_id, close as precio_actual FROM normalized_records WHERE norm_id IN (SELECT MAX(norm_id) FROM normalized_records GROUP BY instrument_id)").fetchall()
        cartera = []
        for r in rows:
            cartera.append({
                "activo": r["instrument_id"],
                "cantidad": 1, # Cantidad ficticia para mostrar
                "precio_actual": r["precio_actual"],
                "valor_total": r["precio_actual"]
            })
        return {"status": "success", "cartera": cartera, "capital_total": sum([c["valor_total"] for c in cartera])}
    finally:
        conn.close()

if __name__ == "__main__":
    print("Iniciando API UNIFICADA en el puerto 8000...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
