import sqlite3
import math
from pathlib import Path

DB_PATH = Path("data/zion.db")

def calcular_riesgo_cartera():
    print("==============================================")
    print(" 🧪 EXPERIMENTO 11: MOTOR DE RIESGO ZION")
    print("==============================================")
    
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        # Agrupamos por instrumento Y fuente para no mezclar precios
        grupos = conn.execute(
            "SELECT DISTINCT instrument_id, source_id FROM normalized_records WHERE quality_status = 'ok'"
        ).fetchall()
        
        print(f"\nSeries detectadas en la base de datos: {len(grupos)}")
        
        precios_historicos = {}
        for inst, source in grupos:
            rows = conn.execute(
                "SELECT close FROM normalized_records WHERE instrument_id = ? AND source_id = ? AND quality_status = 'ok' ORDER BY event_time_utc ASC",
                (inst, source)
            ).fetchall()
            if len(rows) > 1:
                key = f"{inst} ({source})"
                precios_historicos[key] = [r[0] for r in rows]
                print(f"  - {key}: {len(rows)} datos")
        
        if not precios_historicos:
            print("\n[!] No hay suficientes datos históricos.")
            return

        print("\n--- MÉTRICAS DE RIESGO POR SERIE ---")
        retornos_por_activo = {}
        for key, precios in precios_historicos.items():
            retornos = [(precios[i] - precios[i-1]) / precios[i-1] for i in range(1, len(precios)) if precios[i-1] != 0]
            if not retornos: continue
            retornos_por_activo[key] = retornos
            
            media = sum(retornos) / len(retornos)
            varianza = sum((r - media) ** 2 for r in retornos) / len(retornos)
            volatilidad = math.sqrt(varianza)
            var_95 = media - (1.65 * volatilidad)
            
            print(f"  {key}:")
            print(f"    Volatilidad diaria: {volatilidad*100:.4f}%")
            print(f"    VaR 95% (1 día):    {var_95*100:.4f}%")

        if len(retornos_por_activo) >= 2:
            print("\n--- MATRIZ DE CORRELACIÓN ---")
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
                        print(f"  {a} vs {b}: {corr:.4f}")
                    else:
                        print(f"  {a} vs {b}: N/A")

        print("\n==============================================")
    finally:
        conn.close()

if __name__ == "__main__":
    calcular_riesgo_cartera()
