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
        run_id = f"godzilla_{source_id}"
        
        conn.execute("INSERT OR IGNORE INTO runs (run_id, kind, started_at_utc, code_version, params_json, status) VALUES (?,?,?,?,?,?)",
                     (run_id, "ingest", now, "godzilla_v1", "{}", "ok"))
        
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

# --- FUENTES DE DATOS GLOBALES ---

def ingestar_kraken():
    print(" -> [CRIPTO] Kraken...")
    url = "https://api.kraken.com/0/public/Ticker?pair=XBTUSD"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if not data.get("error"):
            key = list(data["result"].keys())[0]
            guardar_en_db("BTC/USD", "crypto", float(data["result"][key]["c"][0]), "kraken")
    except Exception as e:
        print(f"  [ERROR] Kraken: {e}")

def ingestar_yahoo():
    print(" -> [GLOBAL] Yahoo Finance...")
    # Símbolos de Yahoo: SPY (EEUU), QQQ (Nasdaq), ^GDAXI (Alemania), ^FTSE (UK), EURUSD=X (Euro), GC=F (Oro), 0700.HK (Tencent)
    activos = [
        ("SPY", "equity"),
        ("QQQ", "equity"),
        ("^GDAXI", "equity"),  # DAX Alemania
        ("^FTSE", "equity"),   # FTSE Reino Unido
        ("EURUSD=X", "forex"), # Euro/Dólar
        ("GC=F", "commodity"), # Oro
        ("0700.HK", "equity")  # Tencent (Hong Kong)
    ]
    
    for symbol, asset_class in activos:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        try:
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            data = res.json()
            if 'chart' in data and data['chart']['result']:
                precio = data['chart']['result'][0]['meta']['regularMarketPrice']
                inst_id = symbol.replace('^', '').replace('=X', '').replace('=F', '')
                guardar_en_db(inst_id, asset_class, precio, "yahoo")
        except Exception as e:
            print(f"  [ERROR] {symbol}: {e}")

def ingestar_hkma():
    print(" -> [ASIA] HKMA Macro...")
    url = "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/financial/economic-statistics?offset=0"
    try:
        req = requests.get(url, headers={'User-Agent': 'ZION-Godzilla'}, timeout=10)
        data = req.json()
        if 'result' in data and 'records' in data['result']:
            reg = data['result']['records'][-1]
            pib = reg.get('nominal_gdp')
            if pib:
                guardar_en_db("HK_GDP", "macro", float(pib), "hkma")
    except Exception as e:
        print(f"  [ERROR] HKMA: {e}")

if __name__ == "__main__":
    print("\n" + "="*50)
    print(" 🦖 GODZILLA: INGESTA GLOBAL MULTI-MERCADO")
    print("="*50)
    ingestar_kraken()
    ingestar_yahoo()
    ingestar_hkma()
    print("="*50 + "\n")
