"""Pipeline de analítica para ZION Trading Intelligence."""
import argparse
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

from src.analytics.metrics import calculate_returns, max_drawdown, volatility

def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def run_analytics(db_path: str, instrument_id: str):
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Base de datos no encontrada en {db_path}. Ejecuta primero el pipeline sintético.")

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    print(f"[*] Analizando instrumento '{instrument_id}' desde {db_path}...")
    cursor = conn.execute(
        'SELECT close, event_time_utc FROM normalized_records WHERE instrument_id = ? ORDER BY event_time_utc ASC',
        (instrument_id,)
    )
    rows = cursor.fetchall()
    
    if not rows:
        print(f"[!] No se encontraron registros normalizados para {instrument_id}.")
        return

    prices = [float(row["close"]) for row in rows if row["close"] is not None]
    rets = calculate_returns(prices)
    mdd = max_drawdown(prices)
    vol = volatility(rets)

    print(f"    - Total velas analizadas: {len(prices)}")
    print(f"    - Precio inicial: {prices[0] if prices else 0}, Precio final: {prices[-1] if prices else 0}")
    print(f"    - Volatilidad: {vol:.6f}")
    print(f"    - Maximum Drawdown (MDD): {mdd:.6f}")

    # Registrar corrida en 'runs' y evidencia en 'evidence_log'
    now = iso_now()
    run_id = "ana-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    detail = json.dumps({
        "instrument_id": instrument_id,
        "records_count": len(prices),
        "volatility": vol,
        "max_drawdown": mdd
    }, sort_keys=True)

    try:
        conn.execute("BEGIN")
        conn.execute(
            'INSERT INTO runs (run_id, kind, started_at_utc, finished_at_utc, code_version, params_json, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (run_id, 'analytics', now, now, 'v1.0.0', json.dumps({"instrument_id": instrument_id}), 'ok')
        )
        conn.execute(
            'INSERT INTO evidence_log (run_id, kind, message, at_utc) VALUES (?, ?, ?, ?)',
            (run_id, 'check', f"Analítica completada para {instrument_id}: vol={vol:.4f}, mdd={mdd:.4f}", now)
        )
        conn.commit()
        print(f"[+] Corrida de analítica registrada con éxito (run_id: {run_id}).")
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"Error al registrar analítica en DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZION Analytics Pipeline")
    parser.add_argument("--db", default="data/zion.db", help="Ruta a la base de datos SQLite")
    parser.add_argument("--instrument", default="BTC/USD", help="ID del instrumento a analizar")
    args = parser.parse_args()
    run_analytics(args.db, args.instrument)
