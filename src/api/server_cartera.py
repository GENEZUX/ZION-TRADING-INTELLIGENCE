from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import sqlite3
import csv
from pathlib import Path

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "zion.db"
CSV_PATH = REPO_ROOT / "ZProMax_cartera.csv"

@app.get("/api/metricas")
def get_metricas():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        velas = conn.execute("SELECT COUNT(*) FROM normalized_records").fetchone()[0]
        runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        cuarentena = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        return {"total_velas": velas, "total_runs": runs, "total_cuarentena": cuarentena}
    finally:
        conn.close()

@app.get("/api/cartera")
def get_cartera():
    if not CSV_PATH.exists():
        return JSONResponse(status_code=404, content={"error": "Archivo de cartera no encontrado."})
    
    cartera = []
    with open(CSV_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cartera.append({
                "symbol": row["symbol"],
                "quantity": float(row["quantity"]),
                "avg_price": float(row["avg_price"])
            })
    return cartera

@app.get("/api/cartera/csv")
def get_cartera_csv():
    if not CSV_PATH.exists():
        return JSONResponse(status_code=404, content={"error": "Archivo CSV no encontrado."})
    return FileResponse(CSV_PATH, media_type="text/csv", filename="ZProMax_cartera.csv")
