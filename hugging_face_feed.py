from datasets import load_dataset
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("data/zion.db")

def get_utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def save_to_db(instrument_id, asset_class, event_time, open_p, high_p, low_p, close_p, volume, source_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        now = get_utc_now()
        run_id = f"hf_{source_id}"
        
        conn.execute("INSERT OR IGNORE INTO runs (run_id, kind, started_at_utc, code_version, params_json, status) VALUES (?,?,?,?,?,?)",
                     (run_id, "ingest", now, "hf_v1", "{}", "ok"))
        
        payload = json.dumps({"instrument": instrument_id, "event_time": str(event_time)}).encode('utf-8')
        cur = conn.execute("""INSERT INTO raw_records 
            (source_id, run_id, raw_payload, raw_payload_hash, ingested_at_utc)
            VALUES (?, ?, ?, ?, ?)""",
            (source_id, run_id, payload, str(hash(str(event_time) + instrument_id)), now))
        raw_id = cur.lastrowid
        
        conn.execute("""INSERT INTO normalized_records 
            (raw_id, source_id, instrument_id, asset_class, event_time_utc, interval, open, high, low, close, volume, quality_status, ingested_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (raw_id, source_id, instrument_id, asset_class, str(event_time), "1d", 
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

def ingestar_hugging_face():
    print("==============================================")
    print(" 🐉 INGESTA DESDE HUGGING FACE (Datos Reales)")
    print("==============================================")
    
    print("Descargando muestra del dataset 'twelvedata/financial-world-model' (Config: bars_1day)...")
    try:
        # ACÁ ESTÁ EL CAMBIO CLAVE: Agregamos "bars_1day" como configuración
        ds = load_dataset("twelvedata/financial-world-model", "bars_1day", split="train[:200]") 
    except Exception as e:
        print(f"Error descargando el dataset: {e}")
        return

    print(f"Dataset cargado: {len(ds)} filas. Filtrando y guardando...")
    
    # Vemos qué columnas tiene el dataset para adaptarnos
    print(f"Columnas detectadas: {ds.column_names}")
    
    guardados = 0
    for row in ds:
        # Intentamos adaptarnos a los nombres reales del dataset
        instrument_id = row.get("symbol", row.get("ticker", row.get("instrument", "UNKNOWN")))
        
        # A veces el dataset agrupa los datos en una columna 'data'
        if "data" in row and isinstance(row["data"], dict):
            data_dict = row["data"]
        else:
            data_dict = row

        event_time = data_dict.get("datetime", data_dict.get("date", data_dict.get("timestamp", get_utc_now())))
        open_p = data_dict.get("open", 0.0)
        high_p = data_dict.get("high", 0.0)
        low_p = data_dict.get("low", 0.0)
        close_p = data_dict.get("close", 0.0)
        volume = data_dict.get("volume", 0.0)
        
        if close_p and float(close_p) > 0:
            save_to_db(instrument_id, "equity", event_time, open_p, high_p, low_p, close_p, volume, "huggingface")
            guardados += 1
            
        if guardados >= 50: # Guardamos una muestra representativa
            break
            
    print(f"\n¡Éxito! Se guardaron {guardados} velas de Hugging Face en tu base de datos.")

if __name__ == "__main__":
    ingestar_hugging_face()
