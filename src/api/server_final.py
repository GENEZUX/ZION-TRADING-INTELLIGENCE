from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import math
from pathlib import Path


def guardar_huella(metricas, correlaciones):
    conn = sqlite3.connect(str(DB_PATH))
    try:
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for activo, datos in metricas.items():
            corr_destacada = ""
            for par, corr in correlaciones.items():
                if activo in par:
                    corr_destacada = f"{par} = {corr}"
                    break
            conn.execute(
                "INSERT INTO huellas_analisis (instrumento, volatilidad, var_95, correlacion_destacada, fecha_utc) VALUES (?,?,?,?,?)",
                (activo, datos["volatilidad_diaria"], datos["var_95"], corr_destacada, now)
            )
        conn.commit()
    except Exception as e:
        print(f"Error guardando huella: {e}")
    finally:
        conn.close()

app = FastAPI(title="ZION API Final")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "zion.db"

def calcular_riesgo():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        grupos = conn.execute(
            "SELECT DISTINCT instrument_id, source_id FROM normalized_records WHERE quality_status = 'ok'"
        ).fetchall()
        
        precios_historicos = {}
        for inst, source in grupos:
            rows = conn.execute(
                "SELECT close FROM normalized_records WHERE instrument_id = ? AND source_id = ? AND quality_status = 'ok' ORDER BY event_time_utc ASC",
                (inst, source)
            ).fetchall()
            if len(rows) > 1:
                key = f"{inst} ({source})"
                precios_historicos[key] = [r[0] for r in rows]
        
        metricas = {}
        retornos_por_activo = {}
        
        for key, precios in precios_historicos.items():
            retornos = [(precios[i] - precios[i-1]) / precios[i-1] for i in range(1, len(precios)) if precios[i-1] != 0]
            if not retornos: continue
            retornos_por_activo[key] = retornos
            
            media = sum(retornos) / len(retornos)
            varianza = sum((r - media) ** 2 for r in retornos) / len(retornos)
            volatilidad = math.sqrt(varianza)
            var_95 = media - (1.65 * volatilidad)
            
            metricas[key] = {
                "volatilidad_diaria": round(volatilidad * 100, 4),
                "var_95": round(var_95 * 100, 4),
                "datos": len(precios)
            }

        correlaciones = {}
        activos = list(retornos_por_activo.keys())
        for i in range(len(activos)):
            for j in range(i+1, len(activos)):
                a, b = activos[i], activos[j]
                r_a = retornos_por_activo[a]
                r_b = retornos_por_activo[b]
                min_len = min(len(r_a), len(r_b))
                if min_len < 2: continue
                
                media_a = sum(r_a[:min_len]) / min_len
                media_b = sum(r_b[:min_len]) / min_len
                
                cov = sum((r_a[k] - media_a) * (r_b[k] - media_b) for k in range(min_len)) / min_len
                std_a = math.sqrt(sum((x - media_a)**2 for x in r_a[:min_len]) / min_len)
                std_b = math.sqrt(sum((x - media_b)**2 for x in r_b[:min_len]) / min_len)
                
                if std_a > 0 and std_b > 0:
                    corr = cov / (std_a * std_b)
                    correlaciones[f"{a} vs {b}"] = round(corr, 4)

        guardar_huella(metricas, correlaciones)
        return {"metricas": metricas, "correlaciones": correlaciones}
    finally:
        conn.close()

@app.get("/api/metricas")
def get_metricas():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        velas = conn.execute("SELECT COUNT(*) FROM normalized_records").fetchone()[0]
        runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        cuarentena = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        
        # Agregamos los datos de riesgo al mismo JSON de conteos
        riesgo = calcular_riesgo()
        
        return {
            "total_velas": velas,
            "total_runs": runs,
            "total_cuarentena": cuarentena,
            "riesgo": riesgo
        }
    finally:
        conn.close()

@app.get("/api/riesgo")
def get_riesgo():
    return calcular_riesgo()
