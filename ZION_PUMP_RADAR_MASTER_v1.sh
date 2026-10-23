#!/usr/bin/env bash
# =============================================================================
#  ZION PUMP RADAR v1 - MASTERCODE
#  Radar de pumps, squeezes y trampas sobre los perpetuos de ZION.
#
#  Uso:
#    bash ZION_PUMP_RADAR_MASTER_v1.sh serve    # pruebas + build + servidor
#    bash ZION_PUMP_RADAR_MASTER_v1.sh build    # solo genera el HTML
#    bash ZION_PUMP_RADAR_MASTER_v1.sh scan     # corre el escaneo de funding
#    bash ZION_PUMP_RADAR_MASTER_v1.sh test     # solo pruebas
#    bash ZION_PUMP_RADAR_MASTER_v1.sh help
#
#  Variables: ZION_REPO (default /e/SAION/ZION-TRADING-INTELLIGENCE)
#             PORT      (default 8777)
# =============================================================================

set -uo pipefail

REPO="${ZION_REPO:-/e/SAION/ZION-TRADING-INTELLIGENCE}"
PORT="${PORT:-8777}"
RENDERER="$REPO/data/.pump_radar_render.py"
OUT_HTML="$REPO/data/pump_radar.html"

c_gold=$'\033[33m'; c_red=$'\033[31m'; c_grn=$'\033[32m'
c_dim=$'\033[90m';  c_rst=$'\033[0m'; c_bld=$'\033[1m'

say()  { printf '%s\n' "$*"; }
ok()   { printf '%s[OK]%s %s\n' "$c_grn" "$c_rst" "$*"; }
warn() { printf '%s[!]%s %s\n' "$c_gold" "$c_rst" "$*"; }
die()  { printf '%s[ERROR]%s %s\n' "$c_red" "$c_rst" "$*" >&2; exit 1; }

banner() {
    say ""
    say "${c_gold}=======================================================${c_rst}"
    say "${c_gold}  ZION PUMP RADAR v1${c_rst}"
    say "${c_gold}=======================================================${c_rst}"
    say ""
}

find_python() {
    if command -v python >/dev/null 2>&1; then echo "python"; return 0; fi
    if command -v python3 >/dev/null 2>&1; then echo "python3"; return 0; fi
    if [ -x "/c/Users/User/.workbuddy-ai/binaries/python/versions/3.13.12/python.exe" ]; then
        echo "/c/Users/User/.workbuddy-ai/binaries/python/versions/3.13.12/python.exe"; return 0
    fi
    return 1
}

latest_snapshot() {
    ls -1t "$REPO"/data/perp_snapshot_*.json 2>/dev/null | head -1
}

# ---------------------------------------------------------------------------
# Renderer embebido: se escribe una vez y se reutiliza en build y serve.
# ---------------------------------------------------------------------------
write_renderer() {
    mkdir -p "$REPO/data" || die "no puedo crear $REPO/data"
    cat > "$RENDERER" <<'PYEOF'
import json, sys, os, glob
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

REPO = os.environ.get("ZION_REPO", "/e/SAION/ZION-TRADING-INTELLIGENCE")
OUT = os.path.join(REPO, "data", "pump_radar.html")

MAX_OI = 1_000_000.0
MAX_VOL = 1_000_000.0
MAX_FUNDING = 500.0
VOL_OI_TRAP = 8.0
SQUEEZE = -50.0
EUPHORIA = 30.0


def latest_snapshot():
    files = sorted(glob.glob(os.path.join(REPO, "data", "perp_snapshot_*.json")),
                   key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def load():
    path = latest_snapshot()
    if not path:
        raise SystemExit("sin snapshot en data/perp_snapshot_*.json")
    raw = json.load(open(path, encoding="utf-8"))
    return raw.get("captured_at_utc", "?"), raw.get("perps", [])


def compute(captured, perps):
    valid, blocked, traps = [], [], []
    for p in perps:
        oi = float(p.get("open_interest_usd", 0) or 0)
        vol = float(p.get("volume_24h_usd", 0) or 0)
        apr = float(p.get("funding_apr", 0) or 0)
        if oi < MAX_OI or vol < MAX_VOL:
            blocked.append((p, "iliquido"))
            continue
        if abs(apr) > MAX_FUNDING:
            blocked.append((p, "funding_no_fiable"))
        ratio = vol / oi if oi > 0 else 0
        if ratio > VOL_OI_TRAP:
            traps.append((p, ratio))
        valid.append(p)

    def ch(p):
        return float(p.get("change_24h_pct", 0) or 0)

    pumps = sorted(valid, key=ch, reverse=True)[:15]
    squeezes = [p for p in valid if float(p.get("funding_apr", 0) or 0) <= SQUEEZE and ch(p) > 0]
    squeezes.sort(key=lambda p: abs(float(p.get("funding_apr", 0) or 0)), reverse=True)
    euphorias = [p for p in valid
                 if float(p.get("funding_apr", 0) or 0) >= EUPHORIA
                 and float(p.get("open_interest_usd", 1) or 1) > 0
                 and float(p.get("volume_24h_usd", 0) or 0) / float(p.get("open_interest_usd", 1) or 1) > 3]
    euphorias.sort(key=lambda p: float(p.get("funding_apr", 0) or 0), reverse=True)
    traps.sort(key=lambda t: t[1], reverse=True)
    return dict(captured=captured, total=len(perps), valid=len(valid),
                blocked=blocked, pumps=pumps, squeezes=squeezes,
                euphorias=euphorias, traps=traps)


def fmt_money(v):
    v = float(v or 0)
    if v >= 1e9: return f"${v/1e9:.2f}B"
    if v >= 1e6: return f"${v/1e6:.1f}M"
    if v >= 1e3: return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


CSS = """
*{box-sizing:border-box}
body{margin:0;background:#0d1117;color:#c9d1d9;font-family:'Segoe UI',system-ui,sans-serif;padding:28px}
.wrap{max-width:1180px;margin:0 auto}
h1{margin:0;color:#e6b800;font-size:26px;letter-spacing:.5px}
.sub{color:#8b949e;font-size:13px;margin:6px 0 22px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:26px}
.stat{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px}
.stat .k{color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:.6px}
.stat .v{color:#58a6ff;font-size:26px;font-weight:600;margin-top:4px}
h2{color:#e6b800;font-size:15px;margin:26px 0 10px;text-transform:uppercase;letter-spacing:.8px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{color:#8b949e;font-size:11px;text-transform:uppercase;text-align:left;padding:9px 10px;border-bottom:1px solid #30363d}
td{padding:9px 10px;border-bottom:1px solid #21262d}
tr:hover td{background:#161b22}
.tk{color:#e6b800;font-weight:600}
.up{color:#f85149;font-weight:600}
.down{color:#3fb950}
.neg{color:#58a6ff}
.bar{height:7px;border-radius:4px;background:#f85149;min-width:3px}
.bar.blue{background:#58a6ff}
.tag{display:inline-block;background:#21262d;border:1px solid #30363d;border-radius:4px;padding:2px 7px;font-size:10px;color:#8b949e;margin-left:5px}
.empty{color:#8b949e;font-style:italic;padding:10px 0;font-size:13px}
.foot{text-align:center;color:#484f58;font-size:11px;margin-top:36px;letter-spacing:.5px}
code{background:#161b22;padding:2px 6px;border-radius:4px;color:#e6b800;font-size:12px}
"""


def rows_pumps(data):
    if not data["pumps"]:
        return '<p class="empty">sin datos</p>'
    mx = max(abs(float(p.get("change_24h_pct", 0) or 0)) for p in data["pumps"]) or 1
    h = ['<table><thead><tr><th>Activo</th><th>24h</th><th></th>'
         '<th>Precio</th><th>Funding TAE</th><th>OI</th><th>Vol 24h</th></tr></thead><tbody>']
    for p in data["pumps"]:
        ch = float(p.get("change_24h_pct", 0) or 0)
        apr = float(p.get("funding_apr", 0) or 0)
        w = int(abs(ch) / mx * 100)
        cls = "neg" if apr < 0 else ""
        tag = '<span class="tag">shorts pagan</span>' if apr < 0 else ''
        h.append(
            f'<tr><td class="tk">{p.get("symbol")}</td>'
            f'<td class="{"up" if ch >= 0 else "down"}">{ch:+.1f}%</td>'
            f'<td><div class="bar{" blue" if ch < 0 else ""}" style="width:{w}%"></div></td>'
            f'<td>{float(p.get("mark_price", 0) or 0):,.4g}</td>'
            f'<td class="{cls}">{apr:+.2f}%{tag}</td>'
            f'<td>{fmt_money(p.get("open_interest_usd"))}</td>'
            f'<td>{fmt_money(p.get("volume_24h_usd"))}</td></tr>')
    h.append("</tbody></table>")
    return "".join(h)


def rows_squeeze(data):
    if not data["squeezes"]:
        return '<p class="empty">sin squeezes activos</p>'
    h = ['<table><thead><tr><th>Activo</th><th>24h</th><th>Funding TAE</th>'
         '<th>OI</th><th>Lectura</th></tr></thead><tbody>']
    for p in data["squeezes"]:
        apr = float(p.get("funding_apr", 0) or 0)
        ch = float(p.get("change_24h_pct", 0) or 0)
        nota = "squeeze en curso" if ch > 15 else "presion acumulada"
        h.append(f'<tr><td class="tk">{p.get("symbol")}</td>'
                 f'<td class="up">{ch:+.1f}%</td>'
                 f'<td class="neg">{apr:+.2f}%</td>'
                 f'<td>{fmt_money(p.get("open_interest_usd"))}</td>'
                 f'<td>{nota}</td></tr>')
    h.append("</tbody></table>")
    return "".join(h)


def rows_traps(data):
    if not data["traps"]:
        return '<p class="empty">sin rotacion anomala</p>'
    h = ['<table><thead><tr><th>Activo</th><th>24h</th><th>vol/OI</th>'
         '<th>OI</th><th>Lectura</th></tr></thead><tbody>']
    for p, ratio in data["traps"]:
        h.append(f'<tr><td class="tk">{p.get("symbol")}</td>'
                 f'<td class="up">{float(p.get("change_24h_pct",0) or 0):+.1f}%</td>'
                 f'<td class="up">{ratio:.1f}x</td>'
                 f'<td>{fmt_money(p.get("open_interest_usd"))}</td>'
                 f'<td>sin conviccion posicional &mdash; no entrar</td></tr>')
    h.append("</tbody></table>")
    return "".join(h)


def rows_blocked(data):
    if not data["blocked"]:
        return '<p class="empty">nada bloqueado</p>'
    h = ['<table><thead><tr><th>Activo</th><th>Motivo</th><th>Funding TAE</th>'
         '<th>OI</th><th>Vol 24h</th></tr></thead><tbody>']
    for p, motivo in data["blocked"]:
        h.append(f'<tr><td class="tk">{p.get("symbol")}</td>'
                 f'<td>{motivo}</td>'
                 f'<td>{float(p.get("funding_apr",0) or 0):+.2f}%</td>'
                 f'<td>{fmt_money(p.get("open_interest_usd"))}</td>'
                 f'<td>{fmt_money(p.get("volume_24h_usd"))}</td></tr>')
    h.append("</tbody></table>")
    return "".join(h)


def render(data):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    parts = [
        "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<meta http-equiv='refresh' content='30'>",
        "<title>ZION Pump Radar</title><style>", CSS, "</style></head><body><div class='wrap'>",
        "<h1>ZION Pump Radar</h1>",
        f"<p class='sub'>Snapshot {data['captured']} &middot; servido {now} &middot; refresco 30s</p>",
        "<div class='stats'>",
        f"<div class='stat'><div class='k'>Perpetuos</div><div class='v'>{data['total']}</div></div>",
        f"<div class='stat'><div class='k'>Aptos</div><div class='v'>{data['valid']}</div></div>",
        f"<div class='stat'><div class='k'>Squeezes</div><div class='v'>{len(data['squeezes'])}</div></div>",
        f"<div class='stat'><div class='k'>Bloqueados</div><div class='v'>{len(data['blocked'])}</div></div>",
        "</div>",
        "<h2>Top pumps 24h</h2>", rows_pumps(data),
        "<h2>Squeeze de shorts</h2>", rows_squeeze(data),
        "<h2>Trampas de rotacion</h2>", rows_traps(data),
        "<h2>Riesgos bloqueados</h2>", rows_blocked(data),
        "<div class='foot'>ZION Systems &middot; Pump Radar v1 &middot; Generado por la Bestia</div>",
        "</div></body></html>",
    ]
    return "".join(parts)


def build():
    captured, perps = load()
    data = compute(captured, perps)
    html = render(data)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"[OK] HTML generado: {OUT}")
    print(f"     perpetuos={data['total']} aptos={data['valid']} "
          f"squeezes={len(data['squeezes'])} trampas={len(data['traps'])} "
          f"bloqueados={len(data['blocked'])}")
    return 0


def serve(port):
    build()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                captured, perps = load()
                body = render(compute(captured, perps)).encode("utf-8")
                code = 200
            except Exception as exc:
                body = f"<h1>Radar sin datos</h1><pre>{exc}</pre>".encode("utf-8")
                code = 500
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("")
    print(f"  Radar activo en  http://127.0.0.1:{port}")
    print("  Ctrl+C para detener")
    print("")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Radar detenido.")
        srv.server_close()
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "serve":
        port = int(args[1]) if len(args) > 1 else 8777
        sys.exit(serve(port))
    sys.exit(build())
PYEOF
    ok "renderer listo en data/.pump_radar_render.py"
}

# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
cmd_test() {
    say "${c_bld}Pruebas${c_rst}"
    [ -d "$REPO" ] || die "repositorio no encontrado: $REPO"
    ok "repositorio accesible"
    [ -f "$REPO/data/zion.db" ] && ok "base zion.db presente" || warn "sin zion.db (no bloqueante)"
    local snap; snap="$(latest_snapshot)"
    [ -n "$snap" ] && ok "snapshot: $(basename "$snap")" || die "no hay data/perp_snapshot_*.json"
    local py; py="$(find_python)" || die "python no encontrado en PATH"
    ok "python: $py"
    "$py" -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); print('   perps en snapshot:', len(d.get('perps',[])))" "$snap"
}

cmd_build() {
    say "${c_bld}Build${c_rst}"
    write_renderer
    local py; py="$(find_python)" || die "python no encontrado"
    ZION_REPO="$REPO" "$py" "$RENDERER" || die "fallo al renderizar"
    ok "HTML en data/pump_radar.html"
}

cmd_scan() {
    say "${c_bld}Escaneo de funding${c_rst}"
    local py; py="$(find_python)" || die "python no encontrado"
    ( cd "$REPO" && "$py" run_funding_scan.py ) || die "fallo el escaneo"
}

cmd_serve() {
    say "${c_bld}Servidor${c_rst}"
    write_renderer
    local py; py="$(find_python)" || die "python no encontrado"
    ZION_REPO="$REPO" "$py" "$RENDERER" serve "$PORT" || die "el servidor termino con error"
}

cmd_help() {
    cat <<EOF
ZION PUMP RADAR v1 - MasterCode

  bash $(basename "$0") serve    pruebas + build + servidor local
  bash $(basename "$0") build    solo genera el HTML
  bash $(basename "$0") scan     corre el escaneo de funding
  bash $(basename "$0") test     solo pruebas de entorno

Variables:
  ZION_REPO   ruta del repo (default /e/SAION/ZION-TRADING-INTELLIGENCE)
  PORT        puerto del radar (default 8777)

Ejemplo:
  PORT=9000 bash $(basename "$0") serve
EOF
}

banner
case "${1:-help}" in
    serve)  cmd_test; say ""; cmd_serve ;;
    build)  cmd_build ;;
    scan)   cmd_scan ;;
    test)   cmd_test ;;
    help|-h|--help) cmd_help ;;
    *) warn "comando desconocido: $1"; say ""; cmd_help; exit 1 ;;
esac
