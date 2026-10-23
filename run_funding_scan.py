"""ZION — Runner del escaneo de funding en perpetuos.

Uso:
    python run_funding_scan.py                                  # ultimo snapshot conocido
    python run_funding_scan.py data/perp_snapshot_2026-10-22.json
    python run_funding_scan.py <snapshot.json> --json out.json  # volcar resultado
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src" / "analyze"))

from perp_funding import run, print_report  # noqa: E402

DEFAULT_SNAPSHOT = Path("data/perp_snapshot_2026-10-22.json")


def main() -> int:
    ap = argparse.ArgumentParser(description="ZION funding scan")
    ap.add_argument("snapshot", nargs="?", default=str(DEFAULT_SNAPSHOT),
                    help="ruta al snapshot JSON de perpetuos")
    ap.add_argument("--json", dest="json_out", help="volcar el resultado a un JSON")
    args = ap.parse_args()

    snap = Path(args.snapshot)
    if not snap.exists():
        print(f"[ERROR] snapshot no encontrado: {snap}", file=sys.stderr)
        return 1

    result = run(snap)
    print_report(result)

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[OK] resultado volcado en {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
