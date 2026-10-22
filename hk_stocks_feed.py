from datasets import load_dataset
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("data/zion.db")

def get_utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def guardar_en_db(instrument_id, event_time, open_p, high_p, low_p, close_p, volume):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        now = get_utc_now()
        run_id = "feed_hk_stocks"
        conn.execute("INSERT OR IGNORE INTO runs (run_id, kind, started_at_utc, code_version, params_json, status) VALUES (?,?,?,?,?,?)",
                     (run_id, "ingest", now, "hk_v1", "{}", "ok"))
        
        payload = json.dumps({"symbol": instrument_id, "event_time": str(event_time)}).encode('utf-8')
        cur = conn.execute("""INSERT INTO raw_records 
            (source_id, run_id, raw_payload, raw_payload_hash, ingested_at_utc)
            VALUES (?, ?, ?, ?, ?)""",
            ("hkex", run_id, payload, str(hash(str(event_time) + instrument_id)), now))
        raw_id = cur.lastrowid
        
        conn.execute("""INSERT INTO normalized_records 
            (raw_id, source_id, instrument_id, asset_class, event_time_utc, interval, open, high, low, close, volume, quality_status, ingested_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (raw_id, "hkex", instrument_id, "equity", str(event_time), "1d", 
             float(open_p) if open_p else 0.0, 
             float(high_p) if high_p else 0.0, 
             float(low_p) if low_p else 0.0, 
             float(close_p) if close_p else 0.0, 
             float(volume) if volume else 0.0, 
             "ok", now))
        conn.commit()
    except Exception as e:
        print(f"  [ERROR] {instrument_id}: {e}")
    finally:
        conn.close()

def ingestar_hk():
    print(" -> Descargando acciones de Hong Kong desde Hugging Face...")
    try:
        # Usamos el dataset de JinJing que tiene datos de HK unificados 
        ds = load_dataset("cedwyh/jinjing-shared-data", data_files="hk_unified.parquet", split="train[:200]")
    except Exception as e:
        print(f"  [ERROR] Descargando dataset: {e}")
        return

    print(f"Dataset cargado: {len(ds)} filas. Guardando...")
    guardados = 0
    for row in ds:
        symbol = row.get("symbol", "UNKNOWN")
        # El dataset usa 'date', 'open', 'high', 'low', 'close', 'volume' 
        if row.get("close") and float(row["close"]) > 0:
            guardar_en_db(symbol, row.get("date"), row.get("open"), row.get("high"), row.get("low"), row.get("close"), row.get("volume"))
            guardados += 1
        if guardados >= 50:
            break
    print(f"¡Éxito! Se guardaron {guardados} velas de acciones de Hong Kong.")

if __name__ == "__main__":
    ingestar_hk()
