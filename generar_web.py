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

def cargar_senales_funding():
    """Lee las senales del ultimo snapshot de perpetuos. Vacio si no hay tablas."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        existe = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='funding_signals'"
        ).fetchone()[0]
        if not existe:
            return [], None
        rows = conn.execute(
            """SELECT kind, base_asset, venue_long, venue_short, edge_apr, score,
                      rationale, risk_flags_json, captured_at_utc
               FROM funding_signals
               WHERE captured_at_utc = (SELECT MAX(captured_at_utc) FROM funding_signals)
               ORDER BY score DESC"""
        ).fetchall()
        senales = [{
            "kind": r[0], "base_asset": r[1], "venue_long": r[2], "venue_short": r[3],
            "edge_apr": r[4], "score": r[5], "rationale": r[6],
            "flags": json.loads(r[7] or "[]"), "captured": r[8],
        } for r in rows]
        captured = senales[0]["captured"] if senales else None
        return senales, captured
    except sqlite3.Error:
        return [], None
    finally:
        conn.close()


def _bloque_funding(titulo, senales, vacio="(sin senales)"):
    if not senales:
        return f'<h3 class="grp">{titulo}</h3><p class="none">{vacio}</p>'
    html = f'<h3 class="grp">{titulo}</h3>'
    html += ('<table><thead><tr><th>Activo</th><th>Edge / Intensidad</th>'
             '<th>Score</th><th>Detalle</th></tr></thead><tbody>')
    for s in senales:
        flags = "".join(f' <span class="flag">{f}</span>' for f in s["flags"])
        valor = f"{s['edge_apr']:+.2f}% TAE" if s["kind"] == "arbitrage" else f"{s['edge_apr']:+.1f}%"
        html += (f"<tr><td><strong>{s['base_asset']}</strong></td>"
                 f"<td class='green'>{valor}</td>"
                 f"<td>{s['score']}</td>"
                 f"<td>{s['rationale']}{flags}</td></tr>")
    html += "</tbody></table>"
    return html


def _seccion_funding(senales, captured):
    html = "<h2>Se&ntilde;ales de Funding en Perpetuos</h2>"
    if not senales:
        return html + ('<p class="none">Sin escaneos de funding registrados. '
                       'Ejecuta <code>python run_funding_scan.py</code>.</p>')
    html += f'<p class="sub">Snapshot: {captured}</p>'
    arb = [s for s in senales if s["kind"] == "arbitrage"]
    sq = [s for s in senales if s["kind"] == "squeeze"]
    eu = [s for s in senales if s["kind"] == "euphoria"]
    tr = [s for s in senales if s["kind"] == "trampa_rotacion"]
    html += _bloque_funding("Arbitraje delta-neutral", arb,
                            "(sin divergencias ejecutables)")
    html += _bloque_funding("Squeeze de shorts", sq)
    html += _bloque_funding("Euforia de longs", eu)
    html += _bloque_funding("Trampas de rotaci&oacute;n &mdash; no entrar", tr,
                            "(sin rotaci&oacute;n an&oacute;mala)")
    return html


def generar_html():
    metricas, correlaciones = calcular_riesgo()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    velas = conn.execute("SELECT COUNT(*) FROM normalized_records").fetchone()[0]
    runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    cuarentena = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
    conn.close()

    senales_funding, captured_funding = cargar_senales_funding()

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
        .sub {{ color: #8b949e; font-size: 13px; margin-top: -8px; }}
        .grp {{ color: #e6b800; font-size: 15px; margin-top: 26px; margin-bottom: 6px; }}
        .flag {{ display: inline-block; background: #21262d; color: #8b949e; border: 1px solid #30363d; border-radius: 4px; padding: 2px 7px; font-size: 11px; margin-left: 6px; }}
        .none {{ color: #8b949e; font-style: italic; padding: 10px 0; }}
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

    html += """</tbody></table>"""
    html += _seccion_funding(senales_funding, captured_funding)
    html += """
        <div class="footer">ZION Trading Intelligence - Generado por la Bestia</div>
    </div>
</body>
</html>"""
    
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"✅ Web generada en: {OUTPUT_PATH}")

if __name__ == "__main__":
    generar_html()
