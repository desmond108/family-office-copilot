"""statement_parser.py — tuned-statement ingestion, the front half of the pipeline.

Fable's push: the deck starts from Kadir's *already-structured* message; the real
product risk lives in parsing a redacted bank statement. This is a synthetic-input
proof that drives parse -> tuned_statement -> suitability_check end to end, and is
built to SURFACE the hard cases rather than hide them:

  - three different custodian formats (comma CSV, semicolon/European-decimal CSV, JSON)
  - bonds quoted in % of nominal (not price-per-share)
  - multi-currency holdings with FX conversion to a USD base
  - fund house-codes vs ISINs — resolve where mapped, FLAG where not (never guess)
  - illiquid alternatives with manual, stale NAVs — flagged, not silently trusted
  - a Lombard loan -> gross/net/leverage exposed for the (future) leverage check
  - a reconciliation checksum: parsed positions must sum to the custodian's own total
  - account_ref continuity: a stable, PII-free key so month-to-month tracking survives

Run:  python3 statement_parser.py
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from suitability_check import (Bands, Holding, RiskProfile, render,
                               suitability_check, worst_enforcement)

HERE = Path(__file__).parent
STMT_DIR = HERE / "synthetic_statements"
TODAY = date(2026, 7, 3)
STALE_NAV_DAYS = 100   # a manual NAV older than this is flagged for the reader

# FX to USD base. In production this is a live FX feed; here it is a dated static
# table, labelled as such so nobody mistakes it for live.
FX = {"USD": 1.0, "EUR": 1.08, "CHF": 1.11, "SGD": 0.74}
FX_AS_OF = "2026-07-02"
FX_SOURCE = "static demo FX table (wire to a live FX feed)"

# House-code -> instrument resolution. Present => resolved; absent => FLAG (no guess).
HOUSECODE_MAP = {
    "HC-USTREAS5Y": {"identifier": "US91282CJL57", "id_type": "ISIN",
                     "instrument_type": "govt_bond", "issuer": "US Treasury"},
    # "HC-EUEQ" is deliberately NOT here -> it will be flagged unresolved.
}


# --------------------------------------------------------------------------- #

@dataclass
class Position:
    custodian: str
    entity: str
    name: str
    asset_class: str
    instrument_type: str
    identifier: str | None
    id_type: str | None
    currency: str
    mv_ccy: float                 # market value in the position's own currency
    mv_base: float                # converted to USD base
    val_as_of: str
    issuer: str | None = None
    resolved: bool = True
    flags: list[str] = field(default_factory=list)


@dataclass
class ParsedStatement:
    custodian: str
    entity: str
    account_class: str
    base_currency: str
    as_of: str
    stated_total: float
    positions: list[Position]
    liabilities: list[dict]
    recon_delta: float = 0.0
    recon_ok: bool = True


# ---- shared normalisation ------------------------------------------------- #

def _to_usd(amount: float, ccy: str, flags: list[str]) -> float:
    if ccy not in FX:
        flags.append(f"no FX rate for {ccy} — value left unconverted")
        return amount
    return amount * FX[ccy]


def _market_value_ccy(qty: float, price: float, basis: str) -> float:
    if basis == "pct_nominal":        # qty = face/nominal, price = % of par
        return qty * price / 100.0
    return qty * price                # per_share / par_part


def _resolve(identifier: str | None, id_type: str | None, flags: list[str]):
    """Return (identifier, id_type, instrument_type_override, issuer). Flags unresolved house-codes."""
    if id_type == "HOUSE":
        hit = HOUSECODE_MAP.get(identifier)
        if hit:
            return hit["identifier"], hit["id_type"], hit.get("instrument_type"), hit.get("issuer")
        flags.append(f"unresolved house-code '{identifier}' — needs instrument mapping")
        return identifier, "HOUSE", None, None
    return identifier, id_type, None, None


def _meta_from_comments(text: str) -> dict:
    meta = {}
    for ln in text.splitlines():
        if ln.startswith("#"):
            for tok in ln.lstrip("#").split("|"):
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    meta[k.strip()] = v.strip().strip("'").strip('"')
    return meta


# ---- per-custodian adapters ----------------------------------------------- #

def parse_csv_generic(path: Path, sep: str, decimal_comma: bool) -> ParsedStatement:
    text = path.read_text()
    meta = _meta_from_comments(text)
    rows = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    reader = csv.DictReader(rows, delimiter=sep)
    positions: list[Position] = []

    def num(s: str) -> float:
        return float(s.replace(",", ".")) if decimal_comma else float(s)

    for r in reader:
        # tolerate two schemas (English / French headers)
        ident = r.get("identifier") or r.get("code")
        idt = r.get("id_type") or r.get("code_type")
        name = r.get("name") or r.get("libelle")
        aclass = r.get("asset_class") or r.get("classe")
        qty = num(r.get("quantity") or r.get("nominal_ou_qte"))
        price = num(r.get("price") or r.get("cours"))
        ccy = r.get("price_ccy") or r.get("devise")
        basis = r.get("valuation_basis") or r.get("base_valo")
        raw_type = (r.get("type") or r.get("categorie") or "").upper()

        flags: list[str] = []
        ident, idt, itype_override, issuer = _resolve(ident, idt, flags)
        itype = itype_override or {
            "ETF": "equity_etf", "MMF": "money_market", "CASH": "cash",
            "OBLIGATION": "govt_bond" if aclass == "fixed_income" else "bond_etf",
            "FONDS": "equity_etf", "LIQUIDITE": "cash",
        }.get(raw_type, "unknown")

        mv_ccy = _market_value_ccy(qty, price, basis)
        mv_base = _to_usd(mv_ccy, ccy, flags)
        positions.append(Position(
            custodian=meta.get("custodian", path.stem), entity=meta.get("entity", "ENT-A"),
            name=name, asset_class=aclass, instrument_type=itype,
            identifier=ident, id_type=idt, currency=ccy,
            mv_ccy=round(mv_ccy, 2), mv_base=round(mv_base, 2),
            val_as_of=meta.get("as_of", ""), issuer=issuer,
            resolved=(idt != "HOUSE"), flags=flags))

    return ParsedStatement(
        custodian=meta.get("custodian", path.stem), entity=meta.get("entity", "ENT-A"),
        account_class=meta.get("account_class", "custody"),
        base_currency=meta.get("base_ccy", "USD"), as_of=meta.get("as_of", ""),
        stated_total=float(meta.get("stated_total_usd", 0)), positions=positions,
        liabilities=[])


def parse_custodian_a(path: Path) -> ParsedStatement:
    return parse_csv_generic(path, sep=",", decimal_comma=False)   # custodian from meta


def parse_custodian_b(path: Path) -> ParsedStatement:
    return parse_csv_generic(path, sep=";", decimal_comma=True)    # custodian from meta


def parse_custodian_c(path: Path) -> ParsedStatement:
    d = json.loads(path.read_text())
    positions: list[Position] = []
    for p in d["positions"]:
        flags: list[str] = []
        if p.get("valuation") == "manual_nav":
            age = (TODAY - date.fromisoformat(p["nav_as_of"])).days
            if age > STALE_NAV_DAYS:
                flags.append(f"stale manual valuation — NAV as of {p['nav_as_of']} ({age}d old)")
        positions.append(Position(
            custodian=d["custodian"], entity=d.get("entity", "Holdco-2"),
            name=p["name"], asset_class=p["asset_class"],
            instrument_type=p["instrument_type"], identifier=p.get("identifier"),
            id_type=p.get("id_type"), currency="USD",
            mv_ccy=float(p["nav_usd"]), mv_base=float(p["nav_usd"]),
            val_as_of=p.get("nav_as_of", d["as_of"]), flags=flags))
    return ParsedStatement(
        custodian=d["custodian"], entity=d.get("entity", "Holdco-2"),
        account_class=d.get("account_class", "trust"),
        base_currency=d["base_currency"], as_of=d["as_of"],
        stated_total=float(d.get("stated_total_usd", 0)), positions=positions,
        liabilities=d.get("liabilities", []))


# ---- reconciliation + continuity ------------------------------------------ #

def reconcile(st: ParsedStatement, tol_abs: float = 250.0, tol_pct: float = 0.0002) -> ParsedStatement:
    total = sum(p.mv_base for p in st.positions)
    st.recon_delta = round(total - st.stated_total, 2)
    tol = max(tol_abs, tol_pct * st.stated_total)
    st.recon_ok = abs(st.recon_delta) <= tol
    return st


def continuity_key(st: ParsedStatement) -> str:
    """Stable, PII-free account key. If tuning changes these attributes month to
    month, the key changes and month-over-month tracking breaks — the risk Fable named."""
    basis = f"{st.custodian}|{st.entity}|{st.account_class}|{st.base_currency}"
    return hashlib.sha1(basis.encode()).hexdigest()[:10]


def check_continuity(keys: dict[str, str]) -> list[str]:
    store = STMT_DIR / ".account_keys.json"
    prior = json.loads(store.read_text()) if store.is_file() else {}
    notes = []
    for cust, k in keys.items():
        if cust not in prior:
            notes.append(f"{cust}: NEW key {k} (first run — baseline established)")
        elif prior[cust] != k:
            notes.append(f"{cust}: KEY CHANGED {prior[cust]} -> {k} — continuity BROKEN "
                         "(re-redaction altered a stable attribute; performance calc at risk)")
        else:
            notes.append(f"{cust}: key {k} matches prior run — continuity intact")
    store.write_text(json.dumps(keys, indent=2))
    return notes


# ---- to suitability engine ------------------------------------------------ #

def to_holdings(statements: list[ParsedStatement]) -> list[Holding]:
    out = []
    for st in statements:
        for p in st.positions:
            out.append(Holding(
                instrument_id=p.identifier or f"{p.custodian}:{p.name}",
                name=p.name, instrument_type=p.instrument_type, asset_class=p.asset_class,
                market_value_base=p.mv_base, currency=p.currency,
                issuer=p.issuer,
                is_liquid=None))   # inferred (alternatives/real_estate => illiquid)
    return out


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #

def run():
    statements = [
        reconcile(parse_custodian_a(STMT_DIR / "custodianA_uob.csv")),
        reconcile(parse_custodian_b(STMT_DIR / "custodianB_eurobank.csv")),
        reconcile(parse_custodian_c(STMT_DIR / "custodianC_familyoffice.json")),
    ]

    print("=" * 92)
    print("STATEMENT INGESTION  ·  parse -> normalise -> reconcile -> suitability")
    print(f"FX: {FX_SOURCE}, as of {FX_AS_OF}\n")

    all_flags = []
    for st in statements:
        total = sum(p.mv_base for p in st.positions)
        rec = "OK" if st.recon_ok else f"WARN  Δ ${st.recon_delta:,.2f}"
        print(f"── {st.custodian}  [{st.entity} · {st.account_class}]  ({st.as_of})")
        print(f"   positions: {len(st.positions)}   parsed total: ${total:,.2f}   "
              f"stated: ${st.stated_total:,.2f}   reconciliation: {rec}")
        if not st.recon_ok:
            print(f"      ↳ likely accrued interest / rounding not itemised — investigate before use")
        for p in st.positions:
            fx = "" if p.currency == "USD" else f"  [{p.currency}→USD @ {FX[p.currency]}]"
            print(f"     · {p.name[:38]:38} {p.asset_class:12} ${p.mv_base:>12,.2f}{fx}")
            for fl in p.flags:
                print(f"         ⚠ {fl}"); all_flags.append(f"{p.name}: {fl}")
        for lb in st.liabilities:
            print(f"     · LIABILITY {lb['type']:14} ${lb['balance']:>12,.2f}  @ {lb['rate']:.1%}")
        print()

    # Consolidated economics (multi-entity, multi-currency, with leverage)
    gross = sum(p.mv_base for st in statements for p in st.positions)
    debt = sum(abs(lb["balance"]) for st in statements for lb in st.liabilities)
    net = gross - debt
    print("── Consolidated")
    print(f"   gross assets: ${gross:,.2f}   liabilities: ${debt:,.2f}   "
          f"net worth: ${net:,.2f}   leverage (debt/net): {debt/net:.1%}")

    print("\n── Account continuity")
    keys = {st.custodian: continuity_key(st) for st in statements}
    for note in check_continuity(keys):
        print(f"   {note}")

    print("\n── Parse-time data-quality flags")
    print(f"   {len(all_flags)} raised" + ("" if all_flags else " — clean"))

    # Drive the normalised book into the suitability engine
    holdings = to_holdings(statements)
    profile = RiskProfile(
        mandate="advisory",
        allocation_bands={"equity": Bands(0.30, 0.65), "fixed_income": Bands(0.10, 0.40),
                          "commodity": Bands(0.00, 0.25), "cash": Bands(0.05, 0.90)},
        min_liquid_pct=0.10)
    flags = suitability_check(profile, holdings, as_of=TODAY)
    print(f"\n── Suitability on the consolidated book  (gate: {worst_enforcement(flags)})")
    print(render(flags))
    print("\nNote: alternatives + real_estate have no band -> flagged (reciprocal check); "
          "the Lombard loan is parsed and leverage computed, ready for the DV01/leverage "
          "check that suitability_check does not yet run.")


if __name__ == "__main__":
    run()
