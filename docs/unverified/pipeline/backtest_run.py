"""Pipeline de Backtesting para ZION Trading Intelligence."""
import argparse
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

from src.backtest.engine import run_sma_crossover

def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def run_backtest(db_path: str, strategy: str, capital: float, instrument_id: str):
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Base de datos no encontrada en {db_path}. Ejecuta primero el pipeline sintético.")

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    print(f"[*] Ejecutando backtest '{strategy}' para '{instrument_id}' con capital inicial ${capital:,.2f}...")
    cursor = conn.execute(
        'SELECT close, event_time_utc FROM normalized_records WHERE instrument_id = ? ORDER BY event_time_utc ASC',
        (instrument_id,)
    )
    rows = cursor.fetchall()
    
    if not rows:
        print(f"[!] No se encontraron registros normalizados para {instrument_id}.")
        return

    prices = [float(row["close"]) for row in rows if row["close"] is not None]
    
    if strategy == "sma_crossover":
        result = run_sma_crossover(prices, initial_capital=capital)
    else:
        raise ValueError(f"Estrategia desconocida: {strategy}")

    print(f"    - Velas evaluadas: {len(prices)}")
    print(f"    - Capital Final: ${result['final_capital']:,.2f}")
    print(f"    - Retorno Total: {result['return_pct']*100:.2f}%")
    print(f"    - Operaciones totales: {result['trades']}")
    print(f"    - Tasa de acierto (Win Rate): {result['win_rate']*100:.2f}%")

    # Registrar en DB
    now = iso_now()
    run_id = "bt-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    params = json.dumps({"strategy": strategy, "capital": capital, "instrument_id": instrument_id}, sort_keys=True)
    detail = json.dumps(result, sort_keys=True)

    try:
        conn.execute("BEGIN")
        conn.execute(
            'INSERT INTO runs (run_id, kind, started_at_utc, finished_at_utc, code_version, params_json, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (run_id, 'backtest', now, now, 'v1.0.0', params, 'ok')
        )
        conn.execute(
            'INSERT INTO evidence_log (run_id, kind, message, at_utc) VALUES (?, ?, ?, ?)',
            (run_id, 'check', f"Backtest {strategy} completado: retorno={result['return_pct']*100:.2f}%", now)
        )
        conn.commit()
        print(f"[+] Corrida de backtest registrada con éxito (run_id: {run_id}).")
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"Error al registrar backtest en DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZION Backtest Pipeline")
    parser.add_argument("--db", default="data/zion.db", help="Ruta a la base de datos SQLite")
    parser.add_argument("--strategy", default="sma_crossover", help="Estrategia de trading a simular")
    parser.add_argument("--capital", type=float, default=10000.0, help="Capital inicial en USD")
    parser.add_argument("--instrument", default="BTC/USD", help="ID del instrumento")
    args = parser.parse_args()
    run_backtest(args.db, args.strategy, args.capital, args.instrument)
