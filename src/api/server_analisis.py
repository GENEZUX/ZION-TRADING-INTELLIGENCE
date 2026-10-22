from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import math
from pathlib import Path

app = FastAPI(title="ZION Analisis Cuantitativo")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "zion.db"

@app.get("/api/analisis")
def get_analisis(instrument_id: str = "BTC/USD"):
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        # Obtenemos los precios de cierre reales de la base de datos
        rows = conn.execute(
            "SELECT close FROM normalized_records WHERE instrument_id = ? ORDER BY event_time_utc ASC", 
            (instrument_id,)
        ).fetchall()
        
        if len(rows) < 2:
            return {"error": "Se necesitan al menos 2 datos para calcular métricas."}
            
        precios = [row[0] for row in rows]
        
        # 1. Retornos (para volatilidad)
        retornos = [(precios[i] - precios[i-1]) / precios[i-1] for i in range(1, len(precios))]
        media_retornos = sum(retornos) / len(retornos)
        varianza = sum((r - media_retornos) ** 2 for r in retornos) / len(retornos)
        volatilidad = math.sqrt(varianza)
        
        # 2. Máximo Drawdown (la peor caída)
        pico = precios[0]
        max_drawdown = 0
        for precio in precios:
            if precio > pico: pico = precio
            drawdown = (precio - pico) / pico
            if drawdown < max_drawdown: max_drawdown = drawdown
            
        # 3. RSI (Simplificado para el ejemplo)
        # (En un caso real, se usan 14 periodos de ganancias/pérdidas)
        ganancias = sum(r for r in retornos if r > 0)
        perdidas = abs(sum(r for r in retornos if r < 0))
        if perdidas == 0: rsi = 100
        else: rsi = 100 - (100 / (1 + (ganancias / perdidas)))

        return {
            "instrument_id": instrument_id,
            "total_datos": len(precios),
            "precio_actual": precios[-1],
            "volatilidad": round(volatilidad, 6),
            "max_drawdown": round(max_drawdown, 6),
            "rsi": round(rsi, 2),
            "status": "Calculado sobre datos reales"
        }
    finally:
        conn.close()
