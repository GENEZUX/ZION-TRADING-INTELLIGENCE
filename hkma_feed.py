import sqlite3
import urllib.request
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/zion.db")

def get_utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def guardar_macro_hkma():
    print(" -> Consultando HKMA (Datos Macro de Hong Kong)...")
    # Endpoint oficial de estadísticas económicas [citation:1]
    url = "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/financial/economic-statistics?offset=0"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ZION-Trader'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            
            if 'result' not in data or 'records' not in data['result']:
                print("  [ERROR] Formato de respuesta inesperado de HKMA.")
                return
            
            # Tomamos los últimos 5 registros (los más recientes)
            registros = data['result']['records'][-5:]
            
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute("PRAGMA foreign_keys = ON")
                now = get_utc_now()
                run_id = "feed_hkma"
                conn.execute("INSERT OR IGNORE INTO runs (run_id, kind, started_at_utc, code_version, params_json, status) VALUES (?,?,?,?,?,?)",
                             (run_id, "ingest", now, "hkma_v1", "{}", "ok"))
                
                for reg in registros:
                    # Guardamos el PIB nominal como un "precio" macro para el motor de riesgo
                    # El campo end_of_month es el timestamp del dato [citation:1]
                    fecha = reg.get('end_of_month', now)
                    pib = reg.get('nominal_gdp')
                    desempleo = reg.get('unemploy_rate')
                    
                    if pib:
                        # Usamos el PIB como "close" para que entre en el esquema normalized_records
                        # Guardamos también el desempleo en el raw_payload para tenerlo disponible
                        payload = json.dumps({"pib_nominal": pib, "desempleo": desempleo, "fecha": fecha}).encode('utf-8')
                        cur = conn.execute("""INSERT INTO raw_records 
                            (source_id, run_id, raw_payload, raw_payload_hash, ingested_at_utc)
                            VALUES (?, ?, ?, ?, ?)""",
                            ("hkma", run_id, payload, str(hash(fecha)), now))
                        raw_id = cur.lastrowid
                        
                        conn.execute("""INSERT INTO normalized_records 
                            (raw_id, source_id, instrument_id, asset_class, event_time_utc, interval, open, high, low, close, volume, quality_status, ingested_at_utc)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (raw_id, "hkma", "HK_GDP", "macro", fecha, "1M", 
                             float(pib), float(pib), float(pib), float(pib), 0.0, "ok", now))
                        print(f"  [OK] HK_GDP ({fecha}): {pib} M HKD")
                
                conn.commit()
            except Exception as e:
                print(f"  [ERROR] Guardando HKMA: {e}")
            finally:
                conn.close()
                
    except Exception as e:
        print(f"  [ERROR] Consultando HKMA: {e}")

if __name__ == "__main__":
    guardar_macro_hkma()
