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
