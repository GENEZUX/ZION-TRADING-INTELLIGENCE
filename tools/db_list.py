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
