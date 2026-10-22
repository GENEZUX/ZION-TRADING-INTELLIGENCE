"""Motor de Análisis Voltex-1 para ZION.
Bucle de 6 puntos (A-B-C-D) para proyección rápida de mercado.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "zion.db"

def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def ejecutar_bucle_voltex(instrument_id="BTC/USD"):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        # Obtener las últimas 6 velas reales del instrumento
        rows = conn.execute(
            "SELECT close, volume, event_time_utc FROM normalized_records "
            "WHERE instrument_id = ? ORDER BY norm_id DESC LIMIT 6",
            (instrument_id,)
        ).fetchall()

        if len(rows) < 4:
            return {"error": "Datos insuficientes para el bucle Voltex-1 (mínimo 4 velas)."}

        # Invertir para que vayan en orden cronológico
        velas = list(reversed(rows))

        # === EL BUCLE VOLTEX-1 ===
        # Punto A: Lectura de volumen + cambio de precio (Entrada)
        vol_actual = velas[-1]['volume']
        precio_actual = velas[-1]['close']
        precio_anterior = velas[-2]['close']
        cambio_pct = ((precio_actual - precio_anterior) / precio_anterior) * 100 if precio_anterior else 0
        
        # Punto B: Filtrado de ruido (Si el volumen es muy bajo, ignorar)
        if vol_actual <= 0:
            return {"estado": "RUIDO", "mensaje": "Volumen nulo, señal filtrada."}

        # Punto C: Comparación con tendencia previa (Promedio simple de las 4 velas anteriores)
        precios_previos = [v['close'] for v in velas[:-1]]
        tendencia_media = sum(precios_previos) / len(precios_previos)
        
        # Punto D: Cálculo de proyección preliminar
        if cambio_pct > 0.1 and precio_actual > tendencia_media:
            senal = "ALCISTA (COMPRA)"
            fuerza = "Fuerte" if vol_actual > (sum(v['volume'] for v in velas[:-1]) / 4) else "Moderada"
        elif cambio_pct < -0.1 and precio_actual < tendencia_media:
            senal = "BAJISTA (VENTA)"
            fuerza = "Fuerte" if vol_actual > (sum(v['volume'] for v in velas[:-1]) / 4) else "Moderada"
        else:
            senal = "NEUTRAL (ESPERA)"
            fuerza = "Consolidación"

        resultado = {
            "instrumento": instrument_id,
            "precio_actual": precio_actual,
            "cambio_pct": round(cambio_pct, 4),
            "volumen": vol_actual,
            "tendencia_media": round(tendencia_media, 4),
            "senal_voltex": senal,
            "fuerza": fuerza,
            "timestamp": iso_now()
        }

        # Guardar en la auditoría (evidence_log)
        conn.execute(
            "INSERT INTO evidence_log (run_id, kind, message, at_utc) VALUES (?,?,?,?)",
            ("voltex_1", "decision", json.dumps(resultado), iso_now())
        )
        conn.commit()
        
        return resultado
    finally:
        conn.close()

if __name__ == "__main__":
    import pprint
    print("=== EJECUTANDO BUCLE VOLTEX-1 ===")
    res = ejecutar_bucle_voltex("BTC/USD")
    pprint.pprint(res)
