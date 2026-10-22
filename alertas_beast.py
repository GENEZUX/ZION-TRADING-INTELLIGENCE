import sqlite3
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/zion.db")

def revisar_alertas():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Revisando anomalías...")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        # 1. Buscar volatilidad extrema en las últimas huellas
        rows = conn.execute("""
            SELECT instrumento, volatilidad, var_95, fecha_utc 
            FROM huellas_analisis 
            WHERE fecha_utc > datetime('now', '-1 hour')
            ORDER BY id DESC LIMIT 20
        """).fetchall()
        
        if not rows:
            print("No hay datos recientes en la memoria.")
            return

        for row in rows:
            instrumento, vol, var, fecha = row
            if vol > 5.0: # Volatilidad mayor al 5%
                print(f"🚨 ALERTA: {instrumento} tiene volatilidad extrema del {vol}% (VaR: {var}%)")
            elif var < -10.0: # VaR muy negativo
                print(f"🚨 ALERTA: {instrumento} tiene riesgo extremo VaR {var}%")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("🦖 Vigilante ZION iniciado. Ctrl+C para detener.")
    try:
        while True:
            revisar_alertas()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nVigilante detenido.")
