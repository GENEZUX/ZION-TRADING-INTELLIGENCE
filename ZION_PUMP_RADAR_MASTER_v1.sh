#!/usr/bin/env bash
# =============================================================================
#  ZION PUMP RADAR v1 — BASH PURO (sin Python)
#
#  Un solo awk clasifica, ordena y emite las tablas HTML. Bash solo envuelve.
#  Motivo: en Git Bash cada arranque de awk cuesta ~0.5s; con 75 llamadas el
#  script tardaba mas de un minuto. Con una sola pasada tarda menos de 2s.
#
#  Uso:
#    bash ZION_PUMP_RADAR_MASTER_v1.sh serve    # abre y mantiene vivo
#    bash ZION_PUMP_RADAR_MASTER_v1.sh build    # genera el HTML una vez
#    bash ZION_PUMP_RADAR_MASTER_v1.sh watch    # regenera en bucle, sin abrir
#    bash ZION_PUMP_RADAR_MASTER_v1.sh test     # verifica el entorno
#    bash ZION_PUMP_RADAR_MASTER_v1.sh help
#
#  Variables:
#    ZION_REPO   default /e/SAION/ZION-TRADING-INTELLIGENCE
#    INTERVAL    segundos entre regeneraciones (default 30)
# =============================================================================

set -o pipefail

REPO="${ZION_REPO:-/e/SAION/ZION-TRADING-INTELLIGENCE}"
INTERVAL="${INTERVAL:-30}"
OUT="$REPO/data/pump_radar.html"
TMPD="$REPO/data/.radar_tmp"

MIN_LIQ=1000000
MAX_FUNDING=500
TRAP_RATIO=8
SQUEEZE_APR=-50
EUPHORIA_APR=30

c_gold=$'\033[33m'; c_red=$'\033[31m'; c_grn=$'\033[32m'
c_dim=$'\033[90m';  c_rst=$'\033[0m'; c_bld=$'\033[1m'

ok()   { printf '%s[OK]%s %s\n' "$c_grn" "$c_rst" "$*"; }
warn() { printf '%s[!]%s %s\n' "$c_gold" "$c_rst" "$*"; }
die()  { printf '%s[ERROR]%s %s\n' "$c_red" "$c_rst" "$*" >&2; exit 1; }

banner() {
    printf '\n%s=======================================================%s\n' "$c_gold" "$c_rst"
    printf '%s  ZION PUMP RADAR v1 — bash puro%s\n' "$c_gold" "$c_rst"
    printf '%s=======================================================%s\n\n' "$c_gold" "$c_rst"
}

latest_snapshot() {
    ls -1t "$REPO"/data/perp_snapshot_*.json 2>/dev/null | head -1
}

# ---------------------------------------------------------------------------
# El motor: un unico awk. Emite las tablas HTML por stdout y los contadores
# en un fichero aparte.
# ---------------------------------------------------------------------------
write_awk() {
    cat > "$TMPD/render.awk" <<'AWKEOF'
function gs(line, key,   re, m) {
    re = "\"" key "\": \"[^\"]*\""
    if (match(line, re)) {
        m = substr(line, RSTART, RLENGTH)
        sub("\"" key "\": \"", "", m)
        sub("\"$", "", m)
        return m
    }
    return ""
}
function gn(line, key,   re, m) {
    re = "\"" key "\": -?[0-9][0-9.eE+-]*"
    if (match(line, re)) {
        m = substr(line, RSTART, RLENGTH)
        sub("\"" key "\": ", "", m)
        return m + 0
    }
    return 0
}
function money(v) {
    v = v + 0
    if (v >= 1e9) return sprintf("$%.2fB", v / 1e9)
    if (v >= 1e6) return sprintf("$%.1fM", v / 1e6)
    if (v >= 1e3) return sprintf("$%.0fK", v / 1e3)
    return sprintf("$%.0f", v)
}
function pct2(v) { return sprintf("%+.2f%%", v) }
function pct1(v) { return sprintf("%+.1f%%", v) }

BEGIN {
    MINL = ENVIRON["R_MIN"] + 0
    MAXF = ENVIRON["R_MAXF"] + 0
    TRAP = ENVIRON["R_TRAP"] + 0
    SQAPR = ENVIRON["R_SQAPR"] + 0
    EUAPR = ENVIRON["R_EUAPR"] + 0
    COUNTS = ENVIRON["R_COUNTS"]
    total = 0; nv = 0; nq = 0; ne = 0; nt = 0; nb = 0
}

/"symbol"/ {
    s = gs($0, "symbol"); if (s == "") next
    c = gn($0, "change_24h_pct")
    a = gn($0, "funding_apr")
    p = gn($0, "mark_price")
    o = gn($0, "open_interest_usd")
    v = gn($0, "volume_24h_usd")
    total++

    if (o < MINL || v < MINL) {
        nb++; bsym[nb] = s; bmot[nb] = "iliquido"
        bc[nb] = c; ba[nb] = a; bo[nb] = o; bv[nb] = v
        next
    }
    if ((a < 0 ? -a : a) > MAXF) {
        nb++; bsym[nb] = s; bmot[nb] = "funding no fiable"
        bc[nb] = c; ba[nb] = a; bo[nb] = o; bv[nb] = v
    }

    r = (o > 0 ? v / o : 0)
    nv++
    vsym[nv] = s; vc[nv] = c; va[nv] = a; vp[nv] = p
    vo[nv] = o; vv[nv] = v; vr[nv] = r

    if (r > TRAP) { nt++; tsym[nt] = s; tc[nt] = c; trr[nt] = r; to[nt] = o }
    if (a <= SQAPR && c > 0) { nq++; qsym[nq] = s; qc[nq] = c; qa[nq] = a; qo[nq] = o }
    if (a >= EUAPR && r > 3) { ne++; esym[ne] = s; ea[ne] = a; er[ne] = r; eo[ne] = o }
}

END {
    printf "%d %d %d %d %d\n", total, nv, nq, nb, nt > COUNTS
    close(COUNTS)

    mx = 0.0001
    for (i = 1; i <= nv; i++) { x = (vc[i] < 0 ? -vc[i] : vc[i]); if (x > mx) mx = x }

    for (i = 1; i <= nv; i++) idx[i] = i
    for (i = 1; i < nv; i++)
        for (j = i + 1; j <= nv; j++)
            if (vc[idx[j]] > vc[idx[i]]) { t = idx[i]; idx[i] = idx[j]; idx[j] = t }

    print "<h2>Top pumps 24h</h2>"
    if (nv == 0) {
        print "<p class=\"empty\">sin datos</p>"
    } else {
        print "<table><thead><tr><th>Activo</th><th>24h</th><th></th><th>Precio</th><th>Funding TAE</th><th>OI</th><th>Vol 24h</th></tr></thead><tbody>"
        lim = (nv < 15 ? nv : 15)
        for (k = 1; k <= lim; k++) {
            i = idx[k]
            w = int(((vc[i] < 0 ? -vc[i] : vc[i]) / mx) * 100)
            if (w < 3) w = 3
            cls = (vc[i] >= 0 ? "up" : "down")
            tcls = (vc[i] >= 0 ? "" : " blue")
            if (va[i] < 0) { acls = "neg"; tag = " <span class=\"tag\">shorts pagan</span>" }
            else { acls = ""; tag = "" }
            printf "<tr><td class=\"tk\">%s</td><td class=\"%s\">%s</td><td><div class=\"bar%s\" style=\"width:%d%%\"></div></td><td>%s</td><td class=\"%s\">%s%s</td><td>%s</td><td>%s</td></tr>\n", \
                vsym[i], cls, pct1(vc[i]), tcls, w, vp[i], acls, pct2(va[i]), tag, money(vo[i]), money(vv[i])
        }
        print "</tbody></table>"
    }

    for (i = 1; i <= nq; i++) qi[i] = i
    for (i = 1; i < nq; i++)
        for (j = i + 1; j <= nq; j++)
            if ((qa[qi[j]] < 0 ? -qa[qi[j]] : qa[qi[j]]) > (qa[qi[i]] < 0 ? -qa[qi[i]] : qa[qi[i]])) {
                t = qi[i]; qi[i] = qi[j]; qi[j] = t
            }

    print "\n<h2>Squeeze de shorts</h2>"
    if (nq == 0) {
        print "<p class=\"empty\">sin squeezes activos</p>"
    } else {
        print "<table><thead><tr><th>Activo</th><th>24h</th><th>Funding TAE</th><th>OI</th><th>Lectura</th></tr></thead><tbody>"
        for (k = 1; k <= nq; k++) {
            i = qi[k]
            nota = (qc[i] > 15 ? "squeeze en curso" : "presion acumulada")
            printf "<tr><td class=\"tk\">%s</td><td class=\"up\">%s</td><td class=\"neg\">%s</td><td>%s</td><td>%s</td></tr>\n", \
                qsym[i], pct1(qc[i]), pct2(qa[i]), money(qo[i]), nota
        }
        print "</tbody></table>"
    }

    for (i = 1; i <= ne; i++) ei[i] = i
    for (i = 1; i < ne; i++)
        for (j = i + 1; j <= ne; j++)
            if (ea[ei[j]] > ea[ei[i]]) { t = ei[i]; ei[i] = ei[j]; ei[j] = t }

    print "\n<h2>Euforia de longs</h2>"
    if (ne == 0) {
        print "<p class=\"empty\">sin euforia relevante</p>"
    } else {
        print "<table><thead><tr><th>Activo</th><th>Funding TAE</th><th>vol/OI</th><th>OI</th><th>Lectura</th></tr></thead><tbody>"
        for (k = 1; k <= ne; k++) {
            i = ei[k]
            printf "<tr><td class=\"tk\">%s</td><td class=\"up\">%s</td><td>%.1fx</td><td>%s</td><td>longs sobrecargados</td></tr>\n", \
                esym[i], pct2(ea[i]), er[i], money(eo[i])
        }
        print "</tbody></table>"
    }

    for (i = 1; i <= nt; i++) ti[i] = i
    for (i = 1; i < nt; i++)
        for (j = i + 1; j <= nt; j++)
            if (trr[ti[j]] > trr[ti[i]]) { t = ti[i]; ti[i] = ti[j]; ti[j] = t }

    print "\n<h2>Trampas de rotacion</h2>"
    if (nt == 0) {
        print "<p class=\"empty\">sin rotacion anomala</p>"
    } else {
        print "<table><thead><tr><th>Activo</th><th>24h</th><th>vol/OI</th><th>OI</th><th>Lectura</th></tr></thead><tbody>"
        for (k = 1; k <= nt; k++) {
            i = ti[k]
            printf "<tr><td class=\"tk\">%s</td><td class=\"up\">%s</td><td class=\"up\">%.1fx</td><td>%s</td><td>sin conviccion posicional &mdash; no entrar</td></tr>\n", \
                tsym[i], pct1(tc[i]), trr[i], money(to[i])
        }
        print "</tbody></table>"
    }

    print "\n<h2>Riesgos bloqueados</h2>"
    if (nb == 0) {
        print "<p class=\"empty\">nada bloqueado</p>"
    } else {
        print "<table><thead><tr><th>Activo</th><th>Motivo</th><th>24h</th><th>Funding TAE</th><th>OI</th><th>Vol 24h</th></tr></thead><tbody>"
        for (k = 1; k <= nb; k++) {
            printf "<tr><td class=\"tk\">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>\n", \
                bsym[k], bmot[k], pct1(bc[k]), pct2(ba[k]), money(bo[k]), money(bv[k])
        }
        print "</tbody></table>"
    }
}
AWKEOF
}

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
build() {
    local quiet="${1:-}"
    [ -d "$REPO" ] || die "repositorio no encontrado: $REPO"
    local snap; snap="$(latest_snapshot)"
    [ -n "$snap" ] || die "no hay data/perp_snapshot_*.json en $REPO"

    mkdir -p "$TMPD" || die "no puedo crear $TMPD"
    write_awk

    local captured total valid nsq nblk ntr now
    captured=$(sed -n 's/.*"captured_at_utc": "\([^"]*\)".*/\1/p' "$snap" | head -1)
    [ -n "$captured" ] || captured="desconocido"
    now=$(date -u '+%Y-%m-%d %H:%M:%S UTC')

    # ---- UNA sola pasada de awk: clasifica, ordena y emite las tablas ----
    R_MIN="$MIN_LIQ" R_MAXF="$MAX_FUNDING" R_TRAP="$TRAP_RATIO" \
    R_SQAPR="$SQUEEZE_APR" R_EUAPR="$EUPHORIA_APR" R_COUNTS="$TMPD/counts.txt" \
    awk -f "$TMPD/render.awk" "$snap" > "$TMPD/tables.html" \
        || die "fallo el motor awk"

    read -r total valid nsq nblk ntr < "$TMPD/counts.txt" 2>/dev/null
    total=${total:-0}; valid=${valid:-0}; nsq=${nsq:-0}; nblk=${nblk:-0}; ntr=${ntr:-0}

    # ---- Envoltorio HTML ----
    {
    printf '%s\n' '<!DOCTYPE html>'
    printf '%s\n' '<html lang="es"><head><meta charset="UTF-8">'
    printf '%s\n' '<meta name="viewport" content="width=device-width,initial-scale=1">'
    printf '<meta http-equiv="refresh" content="%s">\n' "$INTERVAL"
    printf '%s\n' '<title>ZION Pump Radar</title><style>'
    cat <<'CSSEOF'
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
CSSEOF
    printf '%s\n' '</style></head><body><div class="wrap">'
    printf '%s\n' '<h1>ZION Pump Radar</h1>'
    printf '<p class="sub">Snapshot %s &middot; servido %s &middot; refresco %ss</p>\n' "$captured" "$now" "$INTERVAL"
    printf '%s\n' '<div class="stats">'
    printf '<div class="stat"><div class="k">Perpetuos</div><div class="v">%s</div></div>\n' "$total"
    printf '<div class="stat"><div class="k">Aptos</div><div class="v">%s</div></div>\n' "$valid"
    printf '<div class="stat"><div class="k">Squeezes</div><div class="v">%s</div></div>\n' "$nsq"
    printf '<div class="stat"><div class="k">Bloqueados</div><div class="v">%s</div></div>\n' "$nblk"
    printf '%s\n' '</div>'
    cat "$TMPD/tables.html"
    printf '\n%s\n' '<div class="foot">ZION Systems &middot; Pump Radar v1 &middot; bash puro</div>'
    printf '%s\n' '</div></body></html>'
    } > "$OUT"

    if [ -z "$quiet" ]; then
        ok "HTML generado: data/pump_radar.html"
        printf '     perpetuos=%s aptos=%s squeezes=%s trampas=%s bloqueados=%s\n' \
            "$total" "$valid" "$nsq" "$ntr" "$nblk"
    fi
}

# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
cmd_test() {
    printf '%s\n' "${c_bld}Pruebas${c_rst}"
    [ -d "$REPO" ] || die "repositorio no encontrado: $REPO"
    ok "repositorio accesible"
    [ -f "$REPO/data/zion.db" ] && ok "base zion.db presente" || warn "sin zion.db (no bloqueante)"
    local snap; snap="$(latest_snapshot)"
    [ -n "$snap" ] && ok "snapshot: $(basename "$snap")" || die "no hay data/perp_snapshot_*.json"
    ok "perpetuos en snapshot: $(grep -c '"symbol"' "$snap")"
    local t
    for t in awk sed sort grep date; do
        command -v "$t" >/dev/null 2>&1 && ok "herramienta: $t" || die "falta $t"
    done
}

open_browser() {
    local w
    w=$(cygpath -w "$OUT" 2>/dev/null || printf '%s' "$OUT")
    # OJO: en Git Bash, "cmd.exe /c start" a veces NO retorna nunca y congela
    # el script. Se lanza en segundo plano y con timeout: nunca puede bloquear.
    (
        timeout 6 cmd.exe /c start "" "$w" >/dev/null 2>&1 \
            || timeout 6 explorer.exe "$w" >/dev/null 2>&1
    ) >/dev/null 2>&1 &
    printf '  Navegador: %s\n' "$w"
    printf '  (si no se abrio solo, abre esa ruta a mano)\n'
}

cmd_serve() {
    build
    open_browser
    printf '\n  Radar activo. Refresco cada %ss.\n' "$INTERVAL"
    printf '  Archivo: %s\n' "$OUT"
    printf '  Ctrl+C para detener.\n\n'
    while true; do
        sleep "$INTERVAL"
        build quiet || warn "fallo al regenerar; reintentando"
        printf '%s  [%s] regenerado%s\n' "$c_dim" "$(date '+%H:%M:%S')" "$c_rst"
    done
}

cmd_watch() {
    build
    printf '  Vigilando. Refresco cada %ss. Ctrl+C para detener.\n\n' "$INTERVAL"
    while true; do
        sleep "$INTERVAL"
        build quiet || warn "fallo al regenerar"
        printf '%s  [%s] regenerado%s\n' "$c_dim" "$(date '+%H:%M:%S')" "$c_rst"
    done
}

cmd_help() {
    cat <<EOF
ZION PUMP RADAR v1 — bash puro (sin Python)

  bash $(basename "$0") serve    genera, abre el navegador y mantiene vivo
  bash $(basename "$0") build    solo genera el HTML
  bash $(basename "$0") watch    regenera en bucle, sin abrir navegador
  bash $(basename "$0") test     verifica el entorno

Variables:
  ZION_REPO   ruta del repo (default /e/SAION/ZION-TRADING-INTELLIGENCE)
  INTERVAL    segundos entre refrescos (default 30)

Ejemplo:
  INTERVAL=10 bash $(basename "$0") serve

IMPORTANTE: ejecuta el archivo, NO pegues su contenido en la terminal.
  Correcto:   bash /c/Users/User/Downloads/$(basename "$0") serve
  Incorrecto: copiar y pegar todo el codigo dentro de la terminal
EOF
}

banner
case "${1:-help}" in
    serve)  cmd_test; printf '\n'; cmd_serve ;;
    build)  build ;;
    watch)  cmd_test; printf '\n'; cmd_watch ;;
    test)   cmd_test ;;
    help|-h|--help) cmd_help ;;
    *) warn "comando desconocido: $1"; printf '\n'; cmd_help; exit 1 ;;
esac
