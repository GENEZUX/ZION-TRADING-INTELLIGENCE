import sqlite3
import requests
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/zion.db")

def get_utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def guardar_en_db(instrument_id, asset_class, precio, source_id):
    if precio is None or precio == 0:
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        now = get_utc_now()
        run_id = f"feed_{source_id}"
        
        conn.execute("INSERT OR IGNORE INTO runs (run_id, kind, started_at_utc, code_version, params_json, status) VALUES (?,?,?,?,?,?)",
                     (run_id, "ingest", now, "feed_v1", "{}", "ok"))
        
        payload = json.dumps({"precio": precio, "source": source_id}).encode('utf-8')
        cur = conn.execute("""INSERT INTO raw_records 
            (source_id, run_id, raw_payload, raw_payload_hash, ingested_at_utc)
            VALUES (?, ?, ?, ?, ?)""",
            (source_id, run_id, payload, str(hash(precio)), now))
        raw_id = cur.lastrowid
        
        conn.execute("""INSERT INTO normalized_records 
            (raw_id, source_id, instrument_id, asset_class, event_time_utc, interval, open, high, low, close, volume, quality_status, ingested_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (raw_id, source_id, instrument_id, asset_class, now, "1m", 
             float(precio), float(precio), float(precio), float(precio), 1.0, "ok", now))
        
        conn.commit()
        print(f"  [OK] {instrument_id}: ${precio:.2f}")
    except Exception as e:
        print(f"  [ERROR] {instrument_id}: {e}")
    finally:
        conn.close()

def ingestar_kraken():
    print(" -> Consultando Kraken...")
    url = "https://api.kraken.com/0/public/Ticker?pair=XBTUSD"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if data.get("error"): return
        key = list(data["result"].keys())[0]
        precio = float(data["result"][key]["c"][0])
        guardar_en_db("BTC/USD", "crypto", precio, "kraken")
    except Exception as e:
        print(f"  [ERROR] Kraken: {e}")

def ingestar_yahoo():
    print(" -> Consultando Yahoo Finance...")
    url = "https://query1.finance.yahoo.com/v8/finance/chart/SPY"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        data = res.json()
        precio = data['chart']['result'][0]['meta']['regularMarketPrice']
        guardar_en_db("SPY", "equity", precio, "yahoo")
    except Exception as e:
        print(f"  [ERROR] Yahoo: {e}")

if __name__ == "__main__":
    ingestar_kraken()
    ingestar_yahoo()
