# ZION Trading Intelligence - Especificacion Tecnica

**Version:** 1.2 - Fase 01
**Fecha:** 2026-10-21
**Estado:** aprobada por el usuario el 2026-10-21
**Ambito:** local-first, sin servicios externos obligatorios

---

## 1. Proposito

Convertir datos crudos de mercado en decisiones **trazables, auditables y  
reproducibles**. El sistema observa, mide y reporta. No improvisa.

La pregunta que responde:

> Que esta pasando en el mercado, por que, y que evidencia lo sostiene.

La evidencia queda archivada. No se narra de memoria.

## 2. Reglas de oro (no negociables)

| #  | Regla                                                   | Motivo                                                    |
| -- | ------------------------------------------------------- | --------------------------------------------------------- |
| R1 | Lectura antes que escritura                             | Las fases 01-03 son 100% read-only sobre fuentes externas |
| R2 | Ninguna orden real sin paper trading validado           | Un bug de logica con dinero real es irreversible          |
| R3 | Cero credenciales en el repositorio                     | `.env*` ignorado desde el primer commit                   |
| R4 | Toda decision deja rastro en `audit_log`                | Sin trazabilidad no hay confianza                         |
| R5 | Ninguna dependencia se instala sin aprobacion explicita | El entorno se documenta, no se muta                       |
| R6 | Los scripts son idempotentes                            | Correr dos veces no debe romper nada                      |
| R7 | Reproducibilidad antes que elegancia                    | Mismo input, mismo output, siempre                        |

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

| Situacion                                    | Regla                                                     |
| -------------------------------------------- | --------------------------------------------------------- |
| Claves de API                                | Solo en `.env`, nunca en codigo, nunca en git             |
| Archivos `.env*`                             | Ignorados por `.gitignore` desde el commit inicial        |
| Credenciales en texto plano fuera del `.env` | Prohibido. Si existieron, se rotan                        |
| Logs                                         | Nunca imprimen claves, ni truncadas                       |
| Permisos de lectura de API                   | Minimos: lectura. Retiro y ordenes, solo en fase 06       |
| Endpoints privados                           | Solo con firma HMAC verificada y probados en modo lectura |

Nota del auditor: existe `Z-PRO-MAX/.env.txt` (148 bytes, texto plano) que  
**ningun script referencia**. Debe salir del arbol de trabajo. Si alguna vez  
contuvo claves vivas, hay que rotarlas.

## 7. Entorno verificado

| Componente     | Version              | Estado                  |
| -------------- | -------------------- | ----------------------- |
| Python         | 3.12.10 (`py -3.12`) | OK                      |
| Modulo sqlite3 | 3.49.1               | OK                      |
| git            | 2.49.0.windows.1     | OK                      |
| node / npm     | 24.20.0 / 11.19.0    | OK                      |
| dotnet         | 10.0.402             | OK                      |
| bash           | 5.2.37 (MINGW64)     | OK                      |
| sqlite3 CLI    | ausente              | usar `tools/db_list.py` |
| jq             | ausente              | usar `python -c`        |
| ollama         | instalado            | probe solo bajo demanda |

**Limitacion de plataforma:** `E:` no registra propietario de archivo, por eso  
git exige `safe.directory` para cada repositorio alojado ahi. Ya resuelto para  
este repositorio.

## 8. Hoja de ruta

| Fase | Entregable                                                        | Estado     |
| ---- | ----------------------------------------------------------------- | ---------- |
| 00   | Auditoria local read-only del entorno                             | hecho      |
| 01   | Especificacion, README, manifiesto, estructura, repo inicializado | **actual** |
| 02   | Ingesta: un venue, un instrumento, velas 1h a SQLite              | pendiente  |
| 03   | Analisis: dos indicadores con `inputs_hash` verificable           | pendiente  |
| 04   | Reporte markdown reproducible desde la base                       | pendiente  |
| 05   | Paper trading: senales simuladas, cero ordenes reales             | pendiente  |
| 06   | Conexion live, con limites duros y kill-switch                    | pendiente  |

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

| Riesgo                                         | Impacto                                    | Mitigacion                                 |
| ---------------------------------------------- | ------------------------------------------ | ------------------------------------------ |
| Volumen `E:` sin permisos unix                 | git se niega a operar                      | `safe.directory` por repositorio           |
| `data/` inexistente                            | `sqlite3.connect` falla                    | el mastercode crea el directorio           |
| Mastercode pisa la identidad de git            | se pierde el correo real                   | solo escribe si falta o si se fuerza       |
| Sin `sqlite3` CLI                              | no se puede inspeccionar a mano rapido     | `tools/db_list.py`                         |
| Sin `jq`                                       | parseo JSON incomodo                       | `python -c 'import json,sys...'`           |
| `python` es un alias de shell                  | falla en scripts no interactivos           | invocar `py -3.12` explicitamente          |
| `ollama --version` levanta servicio en Windows | efectos secundarios no deseados            | probe solo con `ZION_AUDIT_PROBE_OLLAMA=1` |
| Precios en coma flotante                       | errores de redondeo en dinero              | TEXT decimal exacto, siempre               |
| Pegar scripts en la terminal                   | bash los ejecuta linea a linea y se rompen | ejecutar con `bash archivo.sh`             |

---

*Este documento es el contrato. Si el codigo y este documento discrepan, el  
documento manda hasta que se decida lo contrario por escrito.*

---

## 12. Bootstrap exception (added v1.2)

`phase01_mastercode.sh` is a one-time bootstrap artifact retained for
auditability. It is not part of the project runtime and must not be executed
again in Phase 02 or later. Its actions are represented by the commit history
(`d939ad9`) and by `docs/history-rewrite-2026-10-21.md`.

## 13. History rewrite note (added v1.2)

On 2026-10-21 the repository's history was rewritten twice via
`git checkout --orphan`. The original three-commit history remains recoverable
via `git reflog` for approximately 90 days. See
`docs/history-rewrite-2026-10-21.md` for details.
