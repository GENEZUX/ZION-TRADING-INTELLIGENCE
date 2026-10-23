import sqlite3
import math
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/zion.db")
OUTPUT_PATH = Path("web_publica/index.html")
OUTPUT_PATH.parent.mkdir(exist_ok=True)

def calcular_riesgo():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        grupos = conn.execute("SELECT DISTINCT instrument_id, source_id FROM normalized_records WHERE quality_status = 'ok'").fetchall()
        precios_historicos = {}
        for inst, source in grupos:
            rows = conn.execute("SELECT close FROM normalized_records WHERE instrument_id = ? AND source_id = ? ORDER BY event_time_utc ASC", (inst, source)).fetchall()
            if len(rows) > 1:
                precios_historicos[f"{inst} ({source})"] = [r[0] for r in rows]
        
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
            metricas[key] = {"volatilidad": round(volatilidad * 100, 4), "var_95": round(var_95 * 100, 4), "datos": len(precios)}

        correlaciones = {}
        activos = list(retornos_por_activo.keys())
        for i in range(len(activos)):
            for j in range(i+1, len(activos)):
                a, b = activos[i], activos[j]
                r_a, r_b = retornos_por_activo[a], retornos_por_activo[b]
                min_len = min(len(r_a), len(r_b))
                if min_len < 2: continue
                media_a, media_b = sum(r_a[:min_len])/min_len, sum(r_b[:min_len])/min_len
                cov = sum((r_a[k] - media_a) * (r_b[k] - media_b) for k in range(min_len)) / min_len
                std_a = math.sqrt(sum((x - media_a)**2 for x in r_a[:min_len]) / min_len)
                std_b = math.sqrt(sum((x - media_b)**2 for x in r_b[:min_len]) / min_len)
                if std_a > 0 and std_b > 0:
                    correlaciones[f"{a} vs {b}"] = round(cov / (std_a * std_b), 4)
        return metricas, correlaciones
    finally:
        conn.close()

def generar_html():
    metricas, correlaciones = calcular_riesgo()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    velas = conn.execute("SELECT COUNT(*) FROM normalized_records").fetchone()[0]
    runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    cuarentena = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
    conn.close()

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>ZION Trading Intelligence - Web</title>
    <style>
        body {{ background: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', sans-serif; padding: 40px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #e6b800; border-bottom: 1px solid #30363d; padding-bottom: 20px; }}
        .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }}
        .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; text-align: center; }}
        .card h3 {{ margin: 0; color: #8b949e; font-size: 14px; text-transform: uppercase; }}
        .card .num {{ font-size: 36px; font-weight: bold; color: #58a6ff; margin-top: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
        th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #30363d; }}
        th {{ color: #8b949e; font-size: 13px; text-transform: uppercase; }}
        .red {{ color: #f85149; }}
        .green {{ color: #3fb950; }}
        .footer {{ text-align: center; color: #8b949e; font-size: 12px; margin-top: 40px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>ZION Trading Intelligence</h1>
        <p>Reporte generado el {fecha}</p>
        
        <div class="grid">
            <div class="card"><h3>Velas</h3><div class="num">{velas}</div></div>
            <div class="card"><h3>Runs</h3><div class="num">{runs}</div></div>
            <div class="card"><h3>Cuarentena</h3><div class="num">{cuarentena}</div></div>
        </div>

        <h2>Motor de Riesgo</h2>
        <table>
            <thead><tr><th>Activo</th><th>Volatilidad</th><th>VaR 95%</th><th>Datos</th></tr></thead>
            <tbody>"""
    
    for activo, m in sorted(metricas.items()):
        color = "red" if m['volatilidad'] > 2 else "green"
        html += f"<tr><td>{activo}</td><td class='{color}'>{m['volatilidad']}%</td><td class='red'>{m['var_95']}%</td><td>{m['datos']}</td></tr>"
    
    html += """</tbody></table>
        <h2>Matriz de Correlación</h2>
        <table>
            <thead><tr><th>Par</th><th>Correlación</th></tr></thead>
            <tbody>"""
            
    for par, corr in sorted(correlaciones.items()):
        color = "red" if abs(corr) > 0.7 else "green"
        html += f"<tr><td>{par}</td><td class='{color}'>{corr}</td></tr>"

    html += """</tbody></table>
        <div class="footer">ZION Trading Intelligence - Generado por la Bestia</div>
    </div>
</body>
</html>"""
    
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"✅ Web generada en: {OUTPUT_PATH}")

if __name__ == "__main__":
    generar_html()
