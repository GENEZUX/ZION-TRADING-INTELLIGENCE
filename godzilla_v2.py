import sqlite3
import requests
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/zion.db")

def get_utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def guardar_en_db(instrument_id, asset_class, open_p, high_p, low_p, close_p, volume, source_id, event_time=None):
    if close_p is None or close_p == 0:
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        now = get_utc_now()
        run_id = f"godzilla_{source_id}"
        if not event_time:
            event_time = now
        
        conn.execute("INSERT OR IGNORE INTO runs (run_id, kind, started_at_utc, code_version, params_json, status) VALUES (?,?,?,?,?,?)",
                     (run_id, "ingest", now, "godzilla_v2", "{}", "ok"))
        
        payload = json.dumps({"precio": close_p, "source": source_id}).encode('utf-8')
        cur = conn.execute("""INSERT INTO raw_records 
            (source_id, run_id, raw_payload, raw_payload_hash, ingested_at_utc)
            VALUES (?, ?, ?, ?, ?)""",
            (source_id, run_id, payload, str(hash(str(close_p) + str(event_time))), now))
        raw_id = cur.lastrowid
        
        conn.execute("""INSERT INTO normalized_records 
            (raw_id, source_id, instrument_id, asset_class, event_time_utc, interval, open, high, low, close, volume, quality_status, ingested_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (raw_id, source_id, instrument_id, asset_class, event_time, "1d", 
             float(open_p), float(high_p), float(low_p), float(close_p), float(volume), "ok", now))
        
        conn.commit()
        print(f"  [OK] {instrument_id}: ${close_p:.2f}")
    except Exception as e:
        print(f"  [ERROR] {instrument_id}: {e}")
    finally:
        conn.close()

def ingestar_yahoo_historico():
    print(" -> [GLOBAL v2] Yahoo Finance (Historial de 10 días)...")
    activos = [
        ("SPY", "equity"), ("QQQ", "equity"), ("^GDAXI", "equity"),
        ("^FTSE", "equity"), ("EURUSD=X", "forex"), ("GC=F", "commodity"), ("0700.HK", "equity")
    ]
    
    for symbol, asset_class in activos:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1mo&interval=1d"
        try:
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            data = res.json()
            if 'chart' in data and data['chart']['result']:
                result = data['chart']['result'][0]
                timestamps = result.get('timestamp', [])
                quotes = result['indicators']['quote'][0]
                
                inst_id = symbol.replace('^', '').replace('=X', '').replace('=F', '')
                
                for i in range(max(0, len(timestamps) - 10), len(timestamps)):
                    t = timestamps[i]
                    fecha = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    guardar_en_db(inst_id, asset_class, 
                                  quotes['open'][i], quotes['high'][i], quotes['low'][i], quotes['close'][i], 
                                  quotes['volume'][i] or 0.0, "yahoo", event_time=fecha)
        except Exception as e:
            print(f"  [ERROR] {symbol}: {e}")

if __name__ == "__main__":
    print("\n" + "="*50)
    print(" 🦖 GODZILLA v2: INGESTA CON HISTORIAL")
    print("="*50)
    ingestar_yahoo_historico()
    print("="*50 + "\n")
