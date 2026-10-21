"""Script para exportar resultados de analítica y backtesting de ZION a JSON y CSV."""
import argparse
import sqlite3
import json
import csv
from pathlib import Path

def export_data(db_path: str, output_dir: str, export_format: str):
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Base de datos no encontrada en {db_path}. Ejecuta primero los pipelines.")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    # Consultar runs de tipo analytics y backtest junto con sus evidencias
    cursor = conn.execute(
        '''
        SELECT r.run_id, r.kind, r.started_at_utc, r.params_json, e.message, e.detail_json
        FROM runs r
        LEFT JOIN evidence_log e ON r.run_id = e.run_id
        WHERE r.kind IN ('analytics', 'backtest')
        ORDER BY r.started_at_utc DESC
        '''
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not rows:
        print("[!] No se encontraron ejecuciones de analítica o backtesting en la base de datos.")
        return

    print(f"[*] Se encontraron {len(rows)} registros de analítica/backtest.")

    # Exportar a JSON
    if export_format in ("json", "both"):
        json_path = out_dir / "zion_results_export.json"
        json_path.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
        print(f"[+] Exportado a JSON: {json_path}")

    # Exportar a CSV
    if export_format in ("csv", "both"):
        csv_path = out_dir / "zion_results_export.csv"
        keys = ["run_id", "kind", "started_at_utc", "params_json", "message", "detail_json"]
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        print(f"[+] Exportado a CSV: {csv_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZION Export Results Tool")
    parser.add_argument("--db", default="data/zion.db", help="Ruta a la base de datos SQLite")
    parser.add_argument("--out", default="exports", help="Directorio de salida para los reportes")
    parser.add_argument("--format", choices=["json", "csv", "both"], default="both", help="Formato de exportación")
    args = parser.parse_args()
    export_data(args.db, args.out, args.format)
