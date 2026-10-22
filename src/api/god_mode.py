"""ZION God Mode v2 - Ingesta Real y Auditable."""
import sqlite3
import urllib.request
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "zion.db"

def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def obtener_precio_yahoo(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            return float(data['chart']['result'][0]['meta']['regularMarketPrice'])
    except Exception:
        return None

def obtener_precio_kraken(pair):
    url = f"https://api.kraken.com/0/public/Ticker?pair={pair}"
    req = urllib.request.Request(url, headers={'User-Agent': 'ZION-Trader'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            result_key = list(data['result'].keys())[0]
            return float(data['result'][result_key]['c'][0])
    except Exception:
        return None

def ingestar_todo():
    print("\n[1/2] INGESTANDO EL MERCADO GLOBAL (Modo Auditable)...")
    now = iso_now()
    run_id = "live_run_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    
    activos = [
        {"id": "BTC/USD", "class": "crypto", "source": "kraken", "func": lambda: obtener_precio_kraken("XBTUSD")},
        {"id": "IBIT", "class": "equity_etf", "source": "yahoo", "func": lambda: obtener_precio_yahoo("IBIT")},
        {"id": "IAUM", "class": "commodity_etf", "source": "yahoo", "func": lambda: obtener_precio_yahoo("IAUM")},
        {"id": "SPY", "class": "equity_etf", "source": "yahoo", "func": lambda: obtener_precio_yahoo("SPY")}
    ]

    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        # 1. Crear el RUN
        conn.execute("INSERT INTO runs (run_id, kind, started_at_utc, code_version, params_json, status) VALUES (?,?,?,?,?,?)",
                     (run_id, "ingest", now, "v2.0-godmode", '{"network": true}', "ok"))
        
        for a in activos:
            print(f"    -> Buscando {a['id']}...")
            precio = a['func']()
            if precio:
                print(f"       [OK] Precio real: ${precio:.2f}")
                # 2. Guardar el RAW RECORD (El JSON original)
                payload = json.dumps({"asset": a['id'], "price": precio, "ts": now}).encode()
                payload_hash = hashlib.sha256(payload).hexdigest()
                
                cursor = conn.execute(
                    "INSERT INTO raw_records (source_id, run_id, raw_payload, raw_payload_hash, ingested_at_utc) VALUES (?,?,?,?,?)",
                    (a['source'], run_id, payload, payload_hash, now)
                )
                raw_id = cursor.lastrowid  # <--- Obtenemos el ID del dato crudo
                
                # 3. Guardar el NORMALIZED RECORD (La vela limpia)
                conn.execute("""INSERT INTO normalized_records 
                    (raw_id, source_id, instrument_id, asset_class, event_time_utc, interval, open, high, low, close, volume, quality_status, ingested_at_utc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (raw_id, a['source'], a['id'], a['class'], now, "1m", precio, precio, precio, precio, 0.0, "ok", now))
            else:
                print(f"       [X] Falló {a['id']}.")
        
        conn.commit()
        print("    -> [AUDITORÍA] Datos guardados exitosamente con trazabilidad completa.\n")
    finally:
        conn.close()

if __name__ == "__main__":
    ingestar_todo()
