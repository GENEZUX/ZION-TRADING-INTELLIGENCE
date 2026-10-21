#!/usr/bin/env bash
# ============================================================================
#
#   >>> NO PEGUES ESTE ARCHIVO EN LA TERMINAL. EJECUTALO. <<<
#
#   bash /e/SAION/ZION-TRADING-INTELLIGENCE/phase01_mastercode.sh
#
# ----------------------------------------------------------------------------
#  ZION Trading Intelligence - FASE 01 MASTERCODE  (v2)
#  Sanea el repositorio, crea la estructura, escribe la documentacion
#  y hace el commit.
#
#  Idempotente. Sin instalaciones. Sin red. Sin credenciales. Sin preguntas.
#  Nunca sobrescribe tu identidad de git ni tus documentos ya editados.
#
#  Variables opcionales:
#    ZION_GIT_NAME="Nombre"     ZION_GIT_EMAIL="correo@real.com"
#    ZION_FORCE_IDENTITY=1      reaplica identidad aunque ya exista
#    ZION_FORCE_DOCS=1          regenera SPECIFICATION.md y README.md
# ============================================================================
set -uo pipefail
export LC_ALL=C

REPO="/e/SAION/ZION-TRADING-INTELLIGENCE"
DEFAULT_NAME="Jose Enrique"
DEFAULT_EMAIL="jose@zion.local"

say()  { printf '\n%s\n' "------------------------------------------------------------"; printf '%s\n' "$*"; printf '%s\n' "------------------------------------------------------------"; }
ok()   { printf '  [ok] %s\n' "$*"; }
skip() { printf '  [--] %s\n' "$*"; }
warn() { printf '  [!!] %s\n' "$*"; }

[ -d "$REPO/.git" ] || { printf 'ERROR: no hay repositorio git en %s\n' "$REPO" >&2; exit 1; }
cd "$REPO" || exit 1

# ---------------------------------------------------------------------------
say "0. AVISO"
printf '  Este script se EJECUTA, no se pega:\n'
printf '    bash %s\n' "$REPO/phase01_mastercode.sh"

# ---------------------------------------------------------------------------
say "1. SANEANDO safe.directory"
# E: es un volumen que no registra propietario (exFAT/FAT32), por eso git se
# queja. Conservamos SOLO entradas que apunten a repositorios reales y
# eliminamos duplicados y basura pegada por accidente (ej: '*n').
KEEP=()
while IFS= read -r d; do
  [ -n "$d" ] || continue
  if [ -d "$d/.git" ]; then
    KEEP+=("$d")
  else
    printf '  [drop] %s  (no es un repositorio)\n' "$d"
  fi
done < <(git config --global --get-all safe.directory 2>/dev/null | awk 'NF && !seen[$0]++')

git config --global --unset-all safe.directory 2>/dev/null || true
git config --global --add safe.directory "$REPO"
for d in "${KEEP[@]:-}"; do
  [ -n "$d" ] || continue
  [ "$d" = "$REPO" ] && continue
  git config --global --add safe.directory "$d"
done
ok "safe.directory limpio ($(git config --global --get-all safe.directory | wc -l) entrada/s)"

# ---------------------------------------------------------------------------
say "2. AJUSTES PARA VOLUMEN SIN PERMISOS UNIX"
git config --local core.filemode false
git config --local core.autocrlf false
ok "core.filemode=false, core.autocrlf=false"

# ---------------------------------------------------------------------------
say "3. IDENTIDAD DEL REPOSITORIO (local, no global)"
# REGLA: no pisar una identidad ya configurada. Solo se escribe si falta,
# si vienen variables de entorno explicitas, o si se fuerza con
# ZION_FORCE_IDENTITY=1. Antes este bloque sobrescribia todo en cada corrida
# y borraba tu correo real. Ya no.
CUR_NAME="$(git config --local user.name  2>/dev/null || true)"
CUR_EMAIL="$(git config --local user.email 2>/dev/null || true)"

if [ "${ZION_FORCE_IDENTITY:-0}" = "1" ] || [ -n "${ZION_GIT_EMAIL:-}" ]; then
  git config --local user.name  "${ZION_GIT_NAME:-${CUR_NAME:-$DEFAULT_NAME}}"
  git config --local user.email "${ZION_GIT_EMAIL:-${CUR_EMAIL:-$DEFAULT_EMAIL}}"
  ok "identidad aplicada (variable de entorno / forzada)"
elif [ -n "$CUR_EMAIL" ]; then
  skip "identidad conservada: ${CUR_NAME} <${CUR_EMAIL}>"
else
  git config --local user.name  "${ZION_GIT_NAME:-$DEFAULT_NAME}"
  git config --local user.email "${ZION_GIT_EMAIL:-$DEFAULT_EMAIL}"
  ok "identidad inicial creada (provisional)"
fi

FINAL_EMAIL="$(git config --local user.email 2>/dev/null || echo '')"
case "$FINAL_EMAIL" in
  *@zion.local|tu@correo.com|*@example.com|"")
    warn "IDENTIDAD PROVISIONAL: $FINAL_EMAIL"
    printf '       Es un marcador, no un correo real. Corrigelo con:\n'
    printf '       ZION_FORCE_IDENTITY=1 ZION_GIT_EMAIL="tucorreo@real.com" \\\n'
    printf '         bash %s\n' "$REPO/phase01_mastercode.sh"
    ;;
  *)
    ok "correo con formato real: $FINAL_EMAIL"
    ;;
esac

# ---------------------------------------------------------------------------
say "4. ESTRUCTURA DE DIRECTORIOS (segun SPECIFICATION.md seccion 4)"
DIRS="src/ingest src/normalize src/store src/analyze src/report data/raw reports tests docs tools"
for d in $DIRS; do
  mkdir -p "$d"
  [ -e "$d/.gitkeep" ] || : > "$d/.gitkeep"
done
ok "$(printf '%s' "$DIRS" | wc -w) directorios listos"
# data/ existe: sin esto sqlite3.connect('data/zion.db') falla con
# "unable to open database file" porque el directorio padre no existe.

# ---------------------------------------------------------------------------
say "5. .gitignore"
cat > .gitignore <<'ZION_GITIGNORE'
# --- secretos: nunca al repositorio ---
.env
.env.*
!.env.example
*.pem
*.key

# --- datos generados ---
*.db
*.sqlite
*.sqlite3
data/raw/*
!data/raw/.gitkeep
reports/*.log
logs/

# --- runtime ---
__pycache__/
*.py[cod]
.venv/
venv/

# --- sistema ---
.DS_Store
Thumbs.db
ZION_GITIGNORE
ok ".gitignore"

# ---------------------------------------------------------------------------
say "6. environment.txt"
cat > environment.txt <<ZION_ENV
# ZION Trading Intelligence - manifiesto de entorno verificado
# Generado por phase01_mastercode.sh - no editar a mano.

os=Windows11/MINGW64_NT-10.0-26200
shell=GNU bash 5.2.37(1)-release
repo=$REPO
filesystem=E: (sin registros de propietario -> safe.directory requerido)

python=3.12.10
python_invocation=py -3.12
sqlite_module=3.49.1
sqlite_cli=NO INSTALADO (usar tools/db_list.py o el modulo python)
git=2.49.0.windows.1
node=24.20.0
npm=11.19.0
dotnet=10.0.402
ollama=instalado (probe solo con ZION_AUDIT_PROBE_OLLAMA=1)
jq=NO INSTALADO (usar python -c)
curl=disponible

data_dir=data/          creado por el mastercode
db_path=data/zion.db    ignorado por git
audit_utc=2026-10-21T15:02:19Z
ZION_ENV
ok "environment.txt"

# ---------------------------------------------------------------------------
# Escribe un documento solo si no existe (o si ZION_FORCE_DOCS=1).
# Asi tus ediciones a mano nunca se pierden al re-ejecutar.
write_doc() {
  local f="$1"
  if [ -f "$f" ] && [ "${ZION_FORCE_DOCS:-0}" != "1" ]; then
    skip "$f (existe, se conserva)"
    cat > /dev/null
    return 0
  fi
  cat > "$f"
  ok "$f"
}

say "7. DOCUMENTACION"
write_doc SPECIFICATION.md <<'ZION_SPEC'
# ZION Trading Intelligence - Especificacion Tecnica

**Version:** 1.1 - Fase 01
**Fecha:** 2026-10-21
**Estado:** aprobada para construccion
**Ambito:** local-first, sin servicios externos obligatorios

---

## 1. Proposito

Convertir datos crudos de mercado en decisiones **trazables, auditables y
reproducibles**. El sistema observa, mide y reporta. No improvisa.

La pregunta que responde:

> Que esta pasando en el mercado, por que, y que evidencia lo sostiene.

La evidencia queda archivada. No se narra de memoria.

## 2. Reglas de oro (no negociables)

| # | Regla | Motivo |
|---|-------|--------|
| R1 | Lectura antes que escritura | Las fases 01-03 son 100% read-only sobre fuentes externas |
| R2 | Ninguna orden real sin paper trading validado | Un bug de logica con dinero real es irreversible |
| R3 | Cero credenciales en el repositorio | `.env*` ignorado desde el primer commit |
| R4 | Toda decision deja rastro en `audit_log` | Sin trazabilidad no hay confianza |
| R5 | Ninguna dependencia se instala sin aprobacion explicita | El entorno se documenta, no se muta |
| R6 | Los scripts son idempotentes | Correr dos veces no debe romper nada |
| R7 | Reproducibilidad antes que elegancia | Mismo input, mismo output, siempre |

## 3. No-objetivos de la Fase 01

- No ejecuta ordenes, ni en papel ni en real.
- No instala paquetes ni levanta servicios.
- No consulta APIs externas ni credenciales.
- No define estrategia de trading: define el **sustrato** donde medirla.

## 4. Arquitectura

Cinco capas, cada una reemplazable sin tocar las demas.

```
  [1] INGESTA      adaptadores por venue -> datos crudos sin transformar
        |
  [2] NORMALIZACION  simbolos, timeframes, zona horaria UTC, tipos exactos
        |
  [3] ALMACEN      SQLite local (un archivo, cero servidores)
        |
  [4] ANALISIS     indicadores, senales, scoring
        |
  [5] REPORTE      markdown + tablas, versionado en el repositorio
```

Principio: cada capa escribe **solo** su salida. Ninguna capa lee el estado
interno de otra. El unico contrato entre capas es el esquema de datos.

### Estructura de directorios

```
ZION-TRADING-INTELLIGENCE/
  SPECIFICATION.md          este documento
  README.md                 punto de entrada
  environment.txt           manifiesto de entorno verificado
  phase01_mastercode.sh     bootstrap idempotente del repositorio
  .gitignore
  src/
    ingest/                 adaptadores de fuente
    normalize/              limpieza y tipado
    store/                  acceso a SQLite
    analyze/                indicadores y senales
    report/                 generacion de reportes
  data/
    raw/                    descargas crudas (ignorado por git)
    zion.db                 base de datos local (ignorada por git)
  reports/                  salidas markdown versionadas
  tests/                    pruebas de contrato del esquema
  docs/                     reglas operativas
  tools/                    utilidades de desarrollo (no parte del producto)
```

Los directorios vacios llevan `.gitkeep` para que git los versione. `data/`
debe existir **antes** de abrir SQLite: sin el, `sqlite3.connect()` falla con
`unable to open database file`, porque no crea directorios padre.

## 5. Modelo de datos

SQLite 3.49 (modulo de Python 3.12). Base unica: `data/zion.db`.

**Reglas de tipado**

- Todo instante es UTC, ISO 8601 con sufijo `Z`. Nunca hora local.
- Precios y volumenes se guardan como **TEXT decimal exacto**. Nunca `float`:
  `0.1 + 0.2` no es `0.3` y en dinero eso es una perdida.
- Toda tabla lleva `ingested_at` para saber cuando entro el dato.

```sql
CREATE TABLE instruments (
  id         TEXT PRIMARY KEY,   -- ej: 'kraken:XBTUSD'
  symbol     TEXT NOT NULL,
  venue      TEXT NOT NULL,
  kind       TEXT NOT NULL,      -- spot | future | index
  quote      TEXT NOT NULL,
  active     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE candles (
  instrument_id TEXT NOT NULL REFERENCES instruments(id),
  ts_utc        TEXT NOT NULL,   -- inicio de la vela, ISO 8601 Z
  tf            TEXT NOT NULL,   -- 1m | 5m | 1h | 1d
  open          TEXT NOT NULL,   -- decimal exacto
  high          TEXT NOT NULL,
  low           TEXT NOT NULL,
  close         TEXT NOT NULL,
  volume        TEXT NOT NULL,
  source        TEXT NOT NULL,
  ingested_at   TEXT NOT NULL,
  PRIMARY KEY (instrument_id, ts_utc, tf)
);

CREATE TABLE signals (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  instrument_id TEXT NOT NULL REFERENCES instruments(id),
  ts_utc        TEXT NOT NULL,
  name          TEXT NOT NULL,   -- ej: 'ema_cross_9_21'
  value         TEXT NOT NULL,
  confidence    TEXT,            -- decimal exacto 0..1
  inputs_hash   TEXT NOT NULL,   -- sha256 de los datos de entrada
  created_at    TEXT NOT NULL
);

CREATE TABLE runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  phase       TEXT NOT NULL,
  status      TEXT NOT NULL,     -- ok | error | aborted
  notes       TEXT
);

CREATE TABLE audit_log (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc  TEXT NOT NULL,
  actor   TEXT NOT NULL,         -- 'system' | 'phase01_mastercode' | ...
  action  TEXT NOT NULL,
  target  TEXT,
  result  TEXT NOT NULL,
  detail  TEXT
);
```

`inputs_hash` es la pieza clave: permite demostrar que una senal se calculo con
exactamente esos datos y no otros. Sin el, un reporte es opinion.

## 6. Seguridad y secretos

| Situacion | Regla |
|-----------|-------|
| Claves de API | Solo en `.env`, nunca en codigo, nunca en git |
| Archivos `.env*` | Ignorados por `.gitignore` desde el commit inicial |
| Credenciales en texto plano fuera del `.env` | Prohibido. Si existieron, se rotan |
| Logs | Nunca imprimen claves, ni truncadas |
| Permisos de lectura de API | Minimos: lectura. Retiro y ordenes, solo en fase 06 |
| Endpoints privados | Solo con firma HMAC verificada y probados en modo lectura |

Nota del auditor: existe `Z-PRO-MAX/.env.txt` (148 bytes, texto plano) que
**ningun script referencia**. Debe salir del arbol de trabajo. Si alguna vez
contuvo claves vivas, hay que rotarlas.

## 7. Entorno verificado

| Componente | Version | Estado |
|------------|---------|--------|
| Python | 3.12.10 (`py -3.12`) | OK |
| Modulo sqlite3 | 3.49.1 | OK |
| git | 2.49.0.windows.1 | OK |
| node / npm | 24.20.0 / 11.19.0 | OK |
| dotnet | 10.0.402 | OK |
| bash | 5.2.37 (MINGW64) | OK |
| sqlite3 CLI | ausente | usar `tools/db_list.py` |
| jq | ausente | usar `python -c` |
| ollama | instalado | probe solo bajo demanda |

**Limitacion de plataforma:** `E:` no registra propietario de archivo, por eso
git exige `safe.directory` para cada repositorio alojado ahi. Ya resuelto para
este repositorio.

## 8. Hoja de ruta

| Fase | Entregable | Estado |
|------|-----------|--------|
| 00 | Auditoria local read-only del entorno | hecho |
| 01 | Especificacion, README, manifiesto, estructura, repo inicializado | **actual** |
| 02 | Ingesta: un venue, un instrumento, velas 1h a SQLite | pendiente |
| 03 | Analisis: dos indicadores con `inputs_hash` verificable | pendiente |
| 04 | Reporte markdown reproducible desde la base | pendiente |
| 05 | Paper trading: senales simuladas, cero ordenes reales | pendiente |
| 06 | Conexion live, con limites duros y kill-switch | pendiente |

Ninguna fase avanza sin que la anterior tenga sus criterios de aceptacion
cumplidos y registrados en `audit_log`.

## 9. Criterios de aceptacion - Fase 01

- [x] Repositorio git inicializado y con commit raiz
- [x] `.gitignore` protege `.env*`, bases de datos y logs
- [x] `environment.txt` refleja el entorno real verificado
- [x] `SPECIFICATION.md` y `README.md` presentes
- [x] Estructura de directorios creada y versionada con `.gitkeep`
- [x] `git status` limpio
- [x] Cero credenciales versionadas
- [x] Script de bootstrap idempotente y no destructivo
- [ ] Identidad de git con correo real (pendiente)

## 10. Riesgos conocidos

| Riesgo | Impacto | Mitigacion |
|--------|---------|------------|
| Volumen `E:` sin permisos unix | git se niega a operar | `safe.directory` por repositorio |
| `data/` inexistente | `sqlite3.connect` falla | el mastercode crea el directorio |
| Mastercode pisa la identidad de git | se pierde el correo real | solo escribe si falta o si se fuerza |
| Sin `sqlite3` CLI | no se puede inspeccionar a mano rapido | `tools/db_list.py` |
| Sin `jq` | parseo JSON incomodo | `python -c 'import json,sys...'` |
| `python` es un alias de shell | falla en scripts no interactivos | invocar `py -3.12` explicitamente |
| `ollama --version` levanta servicio en Windows | efectos secundarios no deseados | probe solo con `ZION_AUDIT_PROBE_OLLAMA=1` |
| Precios en coma flotante | errores de redondeo en dinero | TEXT decimal exacto, siempre |
| Pegar scripts en la terminal | bash los ejecuta linea a linea y se rompen | ejecutar con `bash archivo.sh` |

---

*Este documento es el contrato. Si el codigo y este documento discrepan, el
documento manda hasta que se decida lo contrario por escrito.*
ZION_SPEC

write_doc README.md <<'ZION_README'
# ZION Trading Intelligence

Sistema local de inteligencia de mercado. Observa, mide y reporta con evidencia
archivada. Construido para ser auditado, no para ser creido.

> Estado: **Fase 01** - especificacion aprobada, estructura creada, repositorio
> inicializado. Todavia no opera. Es el plano, no la maquina.

## Inicio rapido

```bash
bash /e/SAION/ZION-TRADING-INTELLIGENCE/phase01_mastercode.sh
```

**Eso es todo.** Una linea. No pegues el contenido del script en la terminal:
bash lo ejecutaria linea por linea y se rompe a la mitad. Se ejecuta, no se pega.

## Que hay aqui

| Archivo | Para que sirve |
|---------|----------------|
| `SPECIFICATION.md` | El contrato: reglas, arquitectura, modelo de datos, fases |
| `environment.txt` | Manifiesto del entorno verificado |
| `phase01_mastercode.sh` | Bootstrap del repositorio. Idempotente y no destructivo |
| `tools/db_list.py` | Inspector read-only de la base SQLite |
| `.gitignore` | Protege secretos, bases de datos y logs |

## Las tres reglas que no se rompen

1. **Lectura primero.** Nada escribe hacia afuera hasta la fase 06.
2. **Nada de dinero real sin paper trading validado.** Sin excepciones.
3. **Cero credenciales en el repositorio.** Nunca. Ni "por un ratito".

## Identidad de git

Este repositorio usa identidad **local** (no global), y el mastercode **no la
sobrescribe** si ya existe. Para cambiarla de forma permanente:

```bash
ZION_FORCE_IDENTITY=1 ZION_GIT_EMAIL="tucorreo@real.com" \
  bash /e/SAION/ZION-TRADING-INTELLIGENCE/phase01_mastercode.sh
git -C /e/SAION/ZION-TRADING-INTELLIGENCE commit --amend --reset-author --no-edit
```

La primera linea cambia la configuracion. La segunda reescribe el autor del
commit raiz (seguro mientras el repositorio no tenga remoto).

Verificar el autor actual:

```bash
git -C /e/SAION/ZION-TRADING-INTELLIGENCE log -1 --format='%an <%ae>'
```

## Inspeccionar la base de datos

No hay `sqlite3` CLI instalado. Usa el inspector del repositorio:

```bash
py -3.12 /e/SAION/ZION-TRADING-INTELLIGENCE/tools/db_list.py
```

Lee `data/zion.db` y lista tablas con su numero de filas. Si la base todavia no
existe, lo dice y no crea nada. Es de solo lectura.

## Notas de plataforma

- `E:` no registra propietario de archivo: git necesita `safe.directory`.
  El mastercode lo gestiona solo.
- No hay `jq`. Usar `py -3.12 -c "import json,sys;print(json.load(sys.stdin))"`.
- `python` es un alias de shell: en scripts usar siempre `py -3.12`.
- `ollama --version` puede levantar un servicio en Windows. Solo se consulta con
  `ZION_AUDIT_PROBE_OLLAMA=1`.

## Siguiente paso

Fase 02: ingesta de un venue, un instrumento, velas de 1h, hacia SQLite.
Antes de escribir codigo, leer la seccion 5 de `SPECIFICATION.md`.
ZION_README

# ---------------------------------------------------------------------------
say "8. tools/db_list.py"
cat > tools/db_list.py <<'ZION_TOOL'
#!/usr/bin/env python3
"""Inspector read-only de la base SQLite de ZION Trading Intelligence.

Uso:
    py -3.12 tools/db_list.py [ruta/a/la/base.db]

No crea, no modifica, no borra. Si la base no existe, lo informa y sale con 0.
"""
import os
import sqlite3
import sys

DEFAULT_DB = os.path.join("data", "zion.db")


def main() -> int:
    db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB
    db_path = os.path.abspath(db_path)

    print(f"base   : {db_path}")
    print(f"sqlite : {sqlite3.sqlite_version}")

    if not os.path.exists(db_path):
        print("estado : NO EXISTE todavia (se crea en la Fase 02)")
        return 0

    uri = "file:" + db_path.replace(os.sep, "/") + "?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        print(f"estado : no se pudo abrir en modo lectura ({exc})")
        return 1

    try:
        tablas = con.execute(
            "select name from sqlite_master where type='table' "
            "and name not like 'sqlite_%' order by name"
        ).fetchall()

        if not tablas:
            print("estado : base vacia, sin tablas")
            return 0

        print(f"estado : {len(tablas)} tabla(s)")
        print()
        print(f"{'tabla':<20} {'filas':>8}")
        print("-" * 30)
        for (nombre,) in tablas:
            filas = con.execute(f'select count(*) from "{nombre}"').fetchone()[0]
            print(f"{nombre:<20} {filas:>8}")
    finally:
        con.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
ZION_TOOL
ok "tools/db_list.py"

# ---------------------------------------------------------------------------
say "9. COMMIT"
git add -A
if git diff --cached --quiet; then
  skip "sin cambios pendientes"
else
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    git commit -q -m "Phase 01: estructura de directorios, inspector de base y docs"
  else
    git commit -q -m "Phase 01: specification, README, environment manifest, bootstrap"
  fi
  ok "commit creado"
fi

# ---------------------------------------------------------------------------
say "RESUMEN"
printf 'Repositorio : %s\n' "$REPO"
printf 'Archivos    : %s versionados\n' "$(git ls-files | wc -l)"
printf 'Estado      : %s cambio(s) pendiente(s)\n' "$(git status --porcelain | wc -l)"
printf 'Autor       : %s <%s>\n' "$(git config --local user.name)" "$(git config --local user.email)"
printf '\nHistorial:\n'
git --no-optional-locks log --oneline 2>/dev/null || printf '  (sin commits)\n'
printf '\nListo. Siguiente: Fase 02 - ingesta.\n'
