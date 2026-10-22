"""Ingesta de precios reales (públicos) desde Kraken.
Cumple R1: Solo lectura. No requiere credenciales.
"""
import requests
import sqlite3
import json
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from src.store.init import DB_PATH, init_db

def fetch_kraken_btc():
    print("Conectando a Kraken (API publica)...")
    # Endpoint publico para obtener las ultimas velas de 1 minuto
    url = "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=1"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    data = res.json()
    
    if data.get("error"):
        raise Exception(f"Error de Kraken: {data['error']}")
    
    # Kraken devuelve {"result": {"XXBTZUSD": [[time, open, high, low, close, vwap, volume, count], ...], "last": ...}}
    pair_key = list(data["result"].keys())[0]
    candles = data["result"][pair_key]
    
    return candles

def save_to_db(candles):
    init_db(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    
    run_id = f"kraken_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Creamos el run
    conn.execute(
        "INSERT INTO runs (run_id, kind, started_at_utc, code_version, params_json, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, "ingest", now, "v1.0", '{"source": "kraken_public"}', "ok")
    )
    
    inserted = 0
    for c in candles:
        ts_unix = int(c[0])
        dt = datetime.fromtimestamp(ts_unix, tz=timezone.utc)
        event_time = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # c: [time, open, high, low, close, vwap, volume, count]
        open_p, high_p, low_p, close_p, volume = float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[6])
        
        raw_payload = json.dumps(c).encode("utf-8")
        payload_hash = hashlib.sha256(raw_payload).hexdigest()
        
        # Insertar en raw_records (ignora si ya existe por el hash)
        conn.execute(
            "INSERT OR IGNORE INTO raw_records (source_id, run_id, raw_payload, raw_payload_hash, ingested_at_utc) "
            "VALUES (?, ?, ?, ?, ?)",
            ("kraken_public", run_id, raw_payload, payload_hash, now)
        )
        
        # Insertar en normalized_records
        conn.execute(
            "INSERT OR IGNORE INTO normalized_records "
            "(source_id, instrument_id, asset_class, event_time_utc, interval, open, high, low, close, volume, quality_status, ingested_at_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("kraken_public", "BTC/USD", "crypto", event_time, "1m", open_p, high_p, low_p, close_p, volume, "ok", now)
        )
        inserted += 1
        
    conn.commit()
    conn.close()
    print(f"✅ Se guardaron {inserted} velas reales de BTC/USD en la base de datos.")
    print(f"   Run ID: {run_id}")

if __name__ == "__main__":
    try:
        candles = fetch_kraken_btc()
        save_to_db(candles)
    except Exception as e:
        print(f"❌ Error: {e}")
