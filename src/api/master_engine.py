"""ZION Master Engine v2 - Ingesta real trazable y API.
"""
import sqlite3
import urllib.request
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import uuid
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "zion.db"

def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def ingestar_datos_reales():
    print("[1/3] Ingestando datos reales de Kraken (BTC/USD)...")
    url = "https://api.kraken.com/0/public/Ticker?pair=XBTUSD"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ZION-Trader'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            precio = float(data['result']['XXBTZUSD']['c'][0])
            print(f"    -> Precio real obtenido: ${precio} USD")
            
            conn = sqlite3.connect(str(DB_PATH))
            try:
                conn.execute("PRAGMA foreign_keys = ON")
                now = iso_now()
                run_id = "live_kraken_btc"
                
                # 1. Insertar el Run
                conn.execute("INSERT OR IGNORE INTO runs (run_id, kind, started_at_utc, code_version, params_json, status) VALUES (?,?,?,?,?,?)",
                             (run_id, "ingest", now, "v2.0", "{}", "ok"))
                
                # 2. Insertar Raw Record (El dato crudo)
                raw_payload = json.dumps({"precio": precio}).encode('utf-8')
                cur = conn.execute("""INSERT INTO raw_records 
                    (source_id, run_id, raw_payload, raw_payload_hash, ingested_at_utc)
                    VALUES (?, ?, ?, ?, ?)""",
                    ("kraken", run_id, raw_payload, str(hash(precio)), now))
                raw_id = cur.lastrowid
                
                # 3. Insertar Normalized Record (El dato listo)
                conn.execute("""INSERT INTO normalized_records 
                    (raw_id, source_id, instrument_id, asset_class, event_time_utc, interval, open, high, low, close, volume, quality_status, ingested_at_utc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (raw_id, "kraken", "BTC/USD", "crypto", now, "1m", precio, precio, precio, precio, 1.0, "ok", now))
                
                conn.commit()
                print("    -> Dato real guardado en SQLite con trazabilidad completa.")
            except Exception as e:
                print(f"    -> Error guardando en DB: {e}")
            finally:
                conn.close()
    except Exception as e:
        print(f"    -> Error consultando Kraken: {e}")

app = FastAPI(title="ZION Trading Intelligence API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/metricas")
def get_metricas():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        velas = conn.execute("SELECT COUNT(*) FROM normalized_records").fetchone()[0]
        runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        cuarentena = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        precio_row = conn.execute("SELECT close, event_time_utc FROM normalized_records WHERE instrument_id='BTC/USD' ORDER BY norm_id DESC LIMIT 1").fetchone()
        return {
            "total_velas": velas,
            "total_runs": runs,
            "total_cuarentena": cuarentena,
            "precio_btc": precio_row["close"] if precio_row else 0,
            "ultima_actualizacion": precio_row["event_time_utc"] if precio_row else "N/A"
        }
    finally:
        conn.close()

FRONTEND_DIR = REPO_ROOT / "src" / "api" / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    ingestar_datos_reales()
    print("[2/3] Iniciando API en http://127.0.0.1:8000 ...")
    try:
        uvicorn.run(app, host="127.0.0.1", port=8000)
    except Exception as e:
        print(f"\n[!] ERROR: El puerto 8000 está ocupado. Cierra la otra ventana de Git Bash donde Uvicorn está corriendo y vuelve a intentar.")
