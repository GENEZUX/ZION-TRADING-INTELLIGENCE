"""ZION — Detector de divergencias de funding en perpetuos.

Filosofia: primero se QUITAN RIESGOS, despues se CONECTA lo que vale.

Puerta 1 (riesgos): descarta activos/pares donde la senal no es ejecutable
o el dato no es fiable. Todo lo descartado se registra con su motivo, nunca
se borra en silencio.

Puerta 2 (valor): solo sobre lo que paso la puerta 1 se buscan tres tipos
de senal con dinero detras:
  - arbitrage : mismo activo, mismo precio, funding divergente entre venues
                (delta-neutral, cobras el funding caro y pagas el barato)
  - squeeze   : funding muy negativo con precio subiendo (shorts atrapados)
  - euphoria  : funding muy positivo con rotacion alta (longs sobrecargados)

Uso:
    python run_funding_scan.py data/perp_snapshot_YYYY-MM-DD.json
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/zion.db")

# ---------------------------------------------------------------------------
# Umbrales de riesgo. Tocar aqui, no en la logica.
# ---------------------------------------------------------------------------

MIN_OI_USD = 1_000_000.0        # interes abierto minimo ejecutable
MIN_VOL_USD = 1_000_000.0       # volumen 24h minimo ejecutable
MAX_PRICE_GAP_PCT = 2.0         # dos venues del "mismo" activo no pueden diferir mas
MAX_ABS_FUNDING_APR = 500.0     # por encima de esto el dato no es fiable para delta-neutral
MIN_EDGE_APR = 3.0              # divergencia minima que justifica abrir dos patas
MAX_VOL_OI_RATIO = 8.0          # volumen >> OI = especulacion intradia, no posicion
SQUEEZE_APR = -50.0             # funding negativo severo
EUPHORIA_APR = 30.0             # funding positivo caro

# Simbolos que representan el mismo subyacente con distinto ticker.
# Se declaran a mano a proposito: adivinar equivalencias es un riesgo.
BASE_ALIASES = {
    "SKHX": "SK_HYNIX",
    "SKHY": "SK_HYNIX",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

@dataclass
class Perp:
    venue: str
    symbol: str
    name: str
    mark_price: float
    change_24h_pct: float
    funding_rate: float
    funding_apr: float
    open_interest_usd: float
    volume_24h_usd: float
    max_leverage: int = 1
    captured_at_utc: str = field(default_factory=utc_now)

    @property
    def base_asset(self) -> str:
        raw = self.symbol
        key = raw.upper()
        if key in BASE_ALIASES:
            return BASE_ALIASES[key]
        # Solo se quita la 'k' de prefijo cuando viene en minuscula (kPEPE).
        # Con 'K' mayuscula (KORU, KIOXIA) el simbolo es completo y se respeta.
        if raw.startswith("k") and raw[1:].isupper():
            return key[1:]
        return key

    @property
    def vol_oi_ratio(self) -> float:
        if self.open_interest_usd <= 0:
            return 0.0
        return self.volume_24h_usd / self.open_interest_usd

    @property
    def uid(self) -> str:
        return f"{self.venue}:{self.symbol}"


@dataclass
class Signal:
    kind: str
    base_asset: str
    venue_long: str
    venue_short: str
    edge_apr: float
    score: float
    rationale: str
    risk_flags: list[str] = field(default_factory=list)
    captured_at_utc: str = field(default_factory=utc_now)


@dataclass
class Reject:
    base_asset: str
    uid: str
    reason: str
    detail: str


# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS perp_snapshots (
    snapshot_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    venue             TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    base_asset        TEXT NOT NULL,
    name              TEXT,
    max_leverage      INTEGER,
    mark_price        REAL NOT NULL,
    change_24h_pct    REAL,
    funding_rate      REAL NOT NULL,
    funding_apr       REAL NOT NULL,
    open_interest_usd REAL,
    volume_24h_usd    REAL,
    vol_oi_ratio      REAL,
    captured_at_utc   TEXT NOT NULL,
    UNIQUE(venue, symbol, captured_at_utc)
);

CREATE TABLE IF NOT EXISTS funding_signals (
    signal_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL,
    base_asset      TEXT NOT NULL,
    venue_long      TEXT,
    venue_short     TEXT,
    edge_apr        REAL,
    score           REAL,
    rationale       TEXT,
    risk_flags_json TEXT,
    captured_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS funding_rejects (
    reject_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    base_asset      TEXT,
    uid             TEXT,
    reason          TEXT NOT NULL,
    detail          TEXT,
    captured_at_utc TEXT NOT NULL
);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

def load_snapshot(path: str | Path) -> list[Perp]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    captured = raw.get("captured_at_utc") or utc_now()
    perps = []
    for item in raw["perps"]:
        perps.append(Perp(
            venue=item["venue"],
            symbol=item["symbol"],
            name=item.get("name", item["symbol"]),
            mark_price=float(item["mark_price"]),
            change_24h_pct=float(item.get("change_24h_pct", 0.0)),
            funding_rate=float(item.get("funding_rate", 0.0)),
            funding_apr=float(item["funding_apr"]),
            open_interest_usd=float(item.get("open_interest_usd", 0.0)),
            volume_24h_usd=float(item.get("volume_24h_usd", 0.0)),
            max_leverage=int(item.get("max_leverage", 1)),
            captured_at_utc=captured,
        ))
    return perps


def save_snapshot(conn: sqlite3.Connection, perps: list[Perp]) -> int:
    rows = [
        (p.venue, p.symbol, p.base_asset, p.name, p.max_leverage, p.mark_price,
         p.change_24h_pct, p.funding_rate, p.funding_apr, p.open_interest_usd,
         p.volume_24h_usd, p.vol_oi_ratio, p.captured_at_utc)
        for p in perps
    ]
    conn.executemany(
        """INSERT OR IGNORE INTO perp_snapshots
           (venue, symbol, base_asset, name, max_leverage, mark_price,
            change_24h_pct, funding_rate, funding_apr, open_interest_usd,
            volume_24h_usd, vol_oi_ratio, captured_at_utc)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# PUERTA 1 — quitar riesgos
# ---------------------------------------------------------------------------

def screen_risks(perps: list[Perp]) -> tuple[list[Perp], list[Reject]]:
    """Devuelve (aptos, rechazados). Un activo rechazado no genera senal."""
    valid: list[Perp] = []
    rejects: list[Reject] = []

    for p in perps:
        if p.open_interest_usd < MIN_OI_USD:
            rejects.append(Reject(p.base_asset, p.uid, "iliquido_oi",
                                  f"OI ${p.open_interest_usd:,.0f} < ${MIN_OI_USD:,.0f}"))
            continue
        if p.volume_24h_usd < MIN_VOL_USD:
            rejects.append(Reject(p.base_asset, p.uid, "iliquido_volumen",
                                  f"Vol ${p.volume_24h_usd:,.0f} < ${MIN_VOL_USD:,.0f}"))
            continue
        if p.mark_price <= 0:
            rejects.append(Reject(p.base_asset, p.uid, "precio_invalido",
                                  f"mark={p.mark_price}"))
            continue
        # Un funding extremo NO se descarta: es informacion. Se bloquea solo
        # para arbitraje (mas abajo), donde el dato debe ser fiable.
        valid.append(p)

    return valid, rejects


def pair_risk(p_a: Perp, p_b: Perp) -> str | None:
    """Motivo por el que dos venues del mismo activo NO son arbitrables."""
    lo, hi = sorted([p_a.mark_price, p_b.mark_price])
    gap_pct = (hi - lo) / lo * 100.0 if lo > 0 else 999.0
    if gap_pct > MAX_PRICE_GAP_PCT:
        return (f"precios_no_comparables: {p_a.uid} {p_a.mark_price:g} vs "
                f"{p_b.uid} {p_b.mark_price:g} (gap {gap_pct:.2f}%)")
    return None


# ---------------------------------------------------------------------------
# PUERTA 2 — conectar lo que vale
# ---------------------------------------------------------------------------

def find_arbitrage(valid: list[Perp], rejects: list[Reject]) -> list[Signal]:
    """Funding divergente entre venues para el mismo subyacente."""
    by_base: dict[str, list[Perp]] = {}
    for p in valid:
        by_base.setdefault(p.base_asset, []).append(p)

    signals: list[Signal] = []

    for base, group in by_base.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                # Mismo mercado exacto = nada que arbitrar. Ojo: dos simbolos
                # distintos bajo el mismo deployer (SKHX/SKHY) SI son pares.
                if a.uid == b.uid:
                    continue

                if abs(a.funding_apr) > MAX_ABS_FUNDING_APR or abs(b.funding_apr) > MAX_ABS_FUNDING_APR:
                    rejects.append(Reject(base, f"{a.uid}|{b.uid}",
                                          "funding_no_fiable_arbitraje",
                                          f"APR {a.funding_apr:+.2f}% / {b.funding_apr:+.2f}% "
                                          f"excede +-{MAX_ABS_FUNDING_APR:.0f}%"))
                    continue

                motivo = pair_risk(a, b)
                if motivo:
                    rejects.append(Reject(base, f"{a.uid}|{b.uid}",
                                          "par_no_comparable", motivo))
                    continue

                # short en el venue que paga mas funding, long en el que paga menos
                hi, lo = (a, b) if a.funding_apr >= b.funding_apr else (b, a)
                edge = hi.funding_apr - lo.funding_apr
                if edge < MIN_EDGE_APR:
                    continue

                liq = min(hi.open_interest_usd, lo.open_interest_usd) / 10_000_000.0
                liq_factor = min(liq, 1.0)
                score = round(edge * liq_factor, 2)

                flags = []
                if min(hi.vol_oi_ratio, lo.vol_oi_ratio) > MAX_VOL_OI_RATIO:
                    flags.append("rotacion_especulativa")

                signals.append(Signal(
                    kind="arbitrage",
                    base_asset=base,
                    venue_long=lo.venue,
                    venue_short=hi.venue,
                    edge_apr=round(edge, 2),
                    score=score,
                    rationale=(f"LONG {lo.symbol}@{lo.venue} ({lo.funding_apr:+.2f}% APR) / "
                               f"SHORT {hi.symbol}@{hi.venue} ({hi.funding_apr:+.2f}% APR) "
                               f"-> {edge:+.2f}% TAE delta-neutral"),
                    risk_flags=flags,
                    captured_at_utc=lo.captured_at_utc,
                ))
    return signals


def find_squeeze(valid: list[Perp]) -> list[Signal]:
    """Shorts pagando caro mientras el precio sube: presion de capitulacion."""
    out: list[Signal] = []
    for p in valid:
        if p.funding_apr <= SQUEEZE_APR and p.change_24h_pct > 0:
            intensidad = min(abs(p.funding_apr) / 50.0, 6.0)
            score = round(intensidad * (1.0 + p.change_24h_pct / 10.0), 2)
            flags = []
            if p.vol_oi_ratio > MAX_VOL_OI_RATIO:
                flags.append("rotacion_especulativa")
            if p.change_24h_pct > 20:
                flags.append("ya_descontado")
            if abs(p.funding_apr) > MAX_ABS_FUNDING_APR:
                flags.append("funding_extremo_verificar")
            out.append(Signal(
                kind="squeeze",
                base_asset=p.base_asset,
                venue_long=p.venue,
                venue_short=p.venue,
                edge_apr=round(p.funding_apr, 2),
                score=score,
                rationale=(f"{p.symbol}@{p.venue}: funding {p.funding_apr:+.2f}% TAE con "
                           f"{p.change_24h_pct:+.1f}% en 24h. Shorts pagando por mantener."),
                risk_flags=flags,
                captured_at_utc=p.captured_at_utc,
            ))
    return sorted(out, key=lambda s: s.score, reverse=True)


def find_euphoria(valid: list[Perp]) -> list[Signal]:
    """Longs pagando caro con rotacion alta: combustible para long squeeze."""
    out: list[Signal] = []
    for p in valid:
        if p.funding_apr >= EUPHORIA_APR and p.vol_oi_ratio > 3.0:
            score = round(p.funding_apr / 10.0 * min(p.vol_oi_ratio / 3.0, 3.0), 2)
            out.append(Signal(
                kind="euphoria",
                base_asset=p.base_asset,
                venue_long=p.venue,
                venue_short=p.venue,
                edge_apr=round(p.funding_apr, 2),
                score=score,
                rationale=(f"{p.symbol}@{p.venue}: funding {p.funding_apr:+.2f}% TAE, "
                           f"vol/OI {p.vol_oi_ratio:.1f}x. Longs sobrecargados."),
                risk_flags=["lado_largo_pagando"],
                captured_at_utc=p.captured_at_utc,
            ))
    return sorted(out, key=lambda s: s.score, reverse=True)


def find_speculative_rotation(valid: list[Perp]) -> list[Signal]:
    """Volumen muy superior al interes abierto: ruido intradia, no posicion.

    Aqui no hay senal de entrada; hay una senal de NO entrar. El precio se
    mueve porque circula papel, no porque alguien este construyendo posicion.
    """
    out: list[Signal] = []
    for p in valid:
        if p.vol_oi_ratio > MAX_VOL_OI_RATIO:
            out.append(Signal(
                kind="trampa_rotacion",
                base_asset=p.base_asset,
                venue_long=p.venue,
                venue_short=p.venue,
                edge_apr=round(p.change_24h_pct, 2),
                score=round(p.vol_oi_ratio, 2),
                rationale=(f"{p.symbol}@{p.venue}: {p.change_24h_pct:+.1f}% en 24h pero "
                           f"vol/OI {p.vol_oi_ratio:.1f}x (OI ${p.open_interest_usd:,.0f}). "
                           f"Movimiento sin conviccion posicional."),
                risk_flags=["sin_construccion_de_posicion"],
                captured_at_utc=p.captured_at_utc,
            ))
    return sorted(out, key=lambda s: s.score, reverse=True)

def persist(conn: sqlite3.Connection, signals: list[Signal], rejects: list[Reject]) -> None:
    now = utc_now()
    conn.executemany(
        """INSERT INTO funding_signals
           (kind, base_asset, venue_long, venue_short, edge_apr, score,
            rationale, risk_flags_json, captured_at_utc)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        [(s.kind, s.base_asset, s.venue_long, s.venue_short, s.edge_apr,
          s.score, s.rationale, json.dumps(s.risk_flags), s.captured_at_utc)
         for s in signals],
    )
    conn.executemany(
        """INSERT INTO funding_rejects
           (base_asset, uid, reason, detail, captured_at_utc)
           VALUES (?,?,?,?,?)""",
        [(r.base_asset, r.uid, r.reason, r.detail, now) for r in rejects],
    )
    conn.commit()


def run(snapshot_path: str | Path, db_path: str | Path = DB_PATH) -> dict:
    perps = load_snapshot(snapshot_path)

    conn = sqlite3.connect(db_path)
    try:
        ensure_schema(conn)
        save_snapshot(conn, perps)

        valid, rejects = screen_risks(perps)
        arb = find_arbitrage(valid, rejects)
        squeeze = find_squeeze(valid)
        euphoria = find_euphoria(valid)
        trampas = find_speculative_rotation(valid)

        signals = arb + squeeze + euphoria + trampas
        persist(conn, signals, rejects)

        return {
            "captured_at_utc": perps[0].captured_at_utc if perps else utc_now(),
            "perps_total": len(perps),
            "aptos": len(valid),
            "rechazados": len(rejects),
            "signals": {
                "arbitrage": len(arb),
                "squeeze": len(squeeze),
                "euphoria": len(euphoria),
                "trampa_rotacion": len(trampas),
            },
            "detalle": {
                "arbitrage": [asdict(s) for s in arb],
                "squeeze": [asdict(s) for s in squeeze[:8]],
                "euphoria": [asdict(s) for s in euphoria[:8]],
                "trampa_rotacion": [asdict(s) for s in trampas[:8]],
                "rejects": [asdict(r) for r in rejects],
            },
        }
    finally:
        conn.close()


def print_report(result: dict) -> None:
    line = "=" * 68
    print(f"\n{line}\n ZION — ESCANEO DE FUNDING EN PERPETUOS\n{line}")
    print(f" Snapshot        : {result['captured_at_utc']}")
    print(f" Activos leidos  : {result['perps_total']}")
    print(f" Pasaron filtro  : {result['aptos']}")
    print(f" Riesgos quitados: {result['rechazados']}")

    arb = result["detalle"]["arbitrage"]
    print(f"\n--- ARBITRAJE DELTA-NEUTRAL ({len(arb)}) ---")
    if not arb:
        print("  (sin divergencias ejecutables en este snapshot)")
    for s in arb:
        print(f"  [{s['score']:>6.2f}] {s['base_asset']:<10} {s['edge_apr']:+7.2f}% TAE")
        print(f"           {s['rationale']}")
        if s["risk_flags"]:
            print(f"           flags: {', '.join(s['risk_flags'])}")

    sq = result["detalle"]["squeeze"]
    print(f"\n--- SQUEEZE DE SHORTS ({len(sq)}) ---")
    if not sq:
        print("  (nada relevante)")
    for s in sq:
        print(f"  [{s['score']:>6.2f}] {s['rationale']}")

    eu = result["detalle"]["euphoria"]
    print(f"\n--- EUFORIA DE LONGS ({len(eu)}) ---")
    if not eu:
        print("  (nada relevante)")
    for s in eu:
        print(f"  [{s['score']:>6.2f}] {s['rationale']}")

    tr = result["detalle"]["trampa_rotacion"]
    print(f"\n--- TRAMPAS DE ROTACION — NO ENTRAR ({len(tr)}) ---")
    if not tr:
        print("  (sin rotacion anomala)")
    for s in tr:
        print(f"  [!{s['score']:>5.1f}x] {s['rationale']}")

    print(f"\n--- RIESGOS QUITADOS ({result['rechazados']}) ---")
    for r in result["detalle"]["rejects"]:
        print(f"  x {r['base_asset']:<10} {r['reason']:<22} {r['detail']}")

    print(f"\n{line}\n")
