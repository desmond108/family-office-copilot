"""Suitability + instruction-diff checks — private-banking port of
Hedge_Fund_260701/risk/pre_trade.py.

pre_trade.py runs 8 absolute VETOES that REJECT a fund trade. Here the same
STRUCTURE (numbered rules, a decision dataclass, severity semantics) evaluates a
client's held book against their risk profile and emits SUITABILITY FLAGS. Note:
this is a PATTERN lift, not a code lift — it shares no lines with pre_trade.py,
which is welded to SQLite / a fixed 20-ticker universe / pandas / long-short.

The `mandate` field decides what a suitability breach *means*:
    execution_only  -> disclose  (do what the client instructs; record unsuitability)
    advisory        -> flag       (needs RM/client sign-off)
    discretionary   -> block      (the app may not hold/act outside the bands)
Two things HARD-BLOCK under every mandate: sanctioned instruments and
complex-product appropriateness (both regulatory, not preference).

v1 changes (from second-reviewer critique):
  - cash is first-class (folded in from cash_balances), not ignored
  - funds vs single securities get different position caps; cash exempt
  - sovereigns exempt from the single-issuer cap
  - FX keyed on economic exposure_currency + hedged flag, not denomination
  - no spurious "near edge" warn at an unbreachable 0% floor / 100% ceiling
  - empty_book routes through the mandate resolver like every other flag
  - preference vs regulatory exclusions split (mandate-driven vs hard)
  - transition plan: a planned phased entry is "on_plan", not a daily breach
  - instruction_diff(): flags where a proposal deviates from the client's own
    explicit instrument spec (the BND-vs-"5yr Treasury" defect)

Dependency-free (stdlib + dataclasses); consumes the objects in data_schema_v0.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# Instrument types treated as single securities for position/issuer caps.
_SINGLE_NAME = {"single_stock", "govt_bond", "corp_bond"}
# Single names whose issuer counts toward issuer concentration (sovereigns exempt).
_ISSUER_TYPES = {"single_stock", "corp_bond"}
# Asset classes that do not count toward the liquidity floor.
_ILLIQUID_CLASSES = {"alternatives", "real_estate"}
# Position types exempt from single-position concentration (parked liquidity).
_POSITION_CAP_EXEMPT_TYPES = {"money_market"}
_POSITION_CAP_EXEMPT_CLASSES = {"cash"}


# --------------------------------------------------------------------------- #
# Inputs (subset of data_schema_v0.md, flattened to what the checks need)
# --------------------------------------------------------------------------- #

@dataclass
class Holding:
    instrument_id: str
    name: str
    instrument_type: str              # equity_etf | bond_etf | money_market | gold_etf | single_stock | ...
    asset_class: str                  # equity | fixed_income | commodity | cash | alternatives | real_estate
    market_value_base: float          # valued in the profile's base currency
    sector: str | None = None         # None / "broad" / "mixed" for diversified funds; tag sector ETFs!
    issuer: str | None = None         # single-name issuer; None for funds
    currency: str = "USD"             # denomination (listing currency)
    exposure_currency: str | None = None   # economic FX exposure; defaults to `currency`
    fx_hedged: bool = False
    is_complex: bool = False          # leveraged / structured / derivative
    is_liquid: bool | None = None     # None => inferred from asset_class
    effective_duration: float | None = None   # years (bonds) — for instruction_diff
    credit: str | None = None         # treasury | corporate | mixed | none — for instruction_diff
    expense_ratio: float | None = None   # % — for the instruction fee screen

    @property
    def fx_ccy(self) -> str:
        return self.exposure_currency or self.currency


@dataclass
class Bands:
    min: float
    max: float


@dataclass
class ConcentrationLimits:
    max_single_security_pct: float = 0.10   # a single stock / bond
    max_single_fund_pct: float = 0.40       # a single diversified fund
    max_single_issuer_pct: float = 0.10     # look-through issuer (single names only)
    max_sector_pct: float = 0.40


@dataclass
class Constraints:
    excluded_asset_classes: list[str] = field(default_factory=list)   # preference (mandate-driven)
    excluded_sectors: list[str] = field(default_factory=list)         # preference
    excluded_instruments: list[str] = field(default_factory=list)     # preference
    sanctioned_instruments: list[str] = field(default_factory=list)   # regulatory (HARD)
    base_currency: str = "USD"
    max_unhedged_fx_pct: float = 0.30


@dataclass
class RiskProfile:
    mandate: str                                      # execution_only | advisory | discretionary
    allocation_bands: dict[str, Bands]                # strategic per-asset-class min/max
    concentration_limits: ConcentrationLimits = field(default_factory=ConcentrationLimits)
    constraints: Constraints = field(default_factory=Constraints)
    min_liquid_pct: float = 0.10
    complex_products_ok: bool = True
    warn_buffer: float = 0.03                         # proximity (abs. weight) that warns before a breach
    # Transition plan: temporarily-wider bands with an expiry, so a *planned*
    # phased entry reads as "on_plan" rather than a daily breach.
    transition_bands: dict[str, Bands] | None = None
    transition_expiry: date | None = None


@dataclass
class ClientInstruction:
    """A structured, explicit client instrument spec (parsed upstream from the
    client message). instruction_diff() checks the proposal against it."""
    label: str
    asset_class: str
    credit: str | None = None                 # required credit: treasury | corporate | any
    max_duration_years: float | None = None   # required max duration
    instrument_type: str | None = None
    target_weight: float | None = None         # client-dictated sleeve weight (of total book)
    weight_tol: float = 0.03                    # tolerance around target_weight
    max_expense_ratio: float | None = None     # client's "low fees" screen, in %
    note: str = ""


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

_ENFORCE_RANK = {"block": 3, "flag": 2, "disclose": 1, "none": 0}


@dataclass
class SuitabilityFlag:
    rule: int
    name: str
    status: str            # ok | warn | on_plan | breach
    detail: str
    domain: str = "suitability"   # suitability | instruction
    hard: bool = False            # regulatory => blocks under any mandate
    enforcement: str = "none"     # resolved from (mandate, status, hard)


def _resolve(mandate: str, status: str, hard: bool) -> str:
    if status == "ok":
        return "none"
    if status in ("warn", "on_plan"):
        return "disclose"
    if hard:                                    # breach of a regulatory rule
        return "block"
    return {                                     # breach of a suitability band
        "execution_only": "disclose",
        "advisory": "flag",
        "discretionary": "block",
    }.get(mandate, "flag")


def _resolve_all(flags: list[SuitabilityFlag], mandate: str) -> list[SuitabilityFlag]:
    for f in flags:
        # instruction deviations contradict an explicit client spec: never softer
        # than 'flag', because someone has to acknowledge the mismatch.
        if f.domain == "instruction" and f.status == "breach":
            f.enforcement = "block" if f.hard else "flag"
        else:
            f.enforcement = _resolve(mandate, f.status, f.hard)
    flags.sort(key=lambda f: (-_ENFORCE_RANK[f.enforcement], f.rule))
    return flags


# --------------------------------------------------------------------------- #
# Suitability check — 8 rules, mirroring pre_trade.py's 8 vetoes
# --------------------------------------------------------------------------- #

def suitability_check(profile: RiskProfile, holdings: list[Holding],
                      cash_balances: dict[str, float] | None = None,
                      as_of: date | None = None) -> list[SuitabilityFlag]:
    as_of = as_of or date.today()

    # Fold cash balances in as first-class holdings (schema keeps them separate).
    book = list(holdings)
    for ccy, amt in (cash_balances or {}).items():
        if amt:
            book.append(Holding(f"CASH_{ccy}", f"Cash ({ccy})", "cash", "cash",
                                float(amt), sector="broad", currency=ccy))

    total = sum(h.market_value_base for h in book)
    if total <= 0:
        return _resolve_all(
            [SuitabilityFlag(0, "empty_book", "breach", "No positions to evaluate.")],
            profile.mandate)

    w: dict[str, float] = {}
    class_w: dict[str, float] = {}
    sector_w: dict[str, float] = {}
    issuer_w: dict[str, float] = {}
    fx_unhedged = 0.0
    liquid = 0.0
    by_id: dict[str, Holding] = {}
    for h in book:
        ww = h.market_value_base / total
        w[h.instrument_id] = w.get(h.instrument_id, 0.0) + ww
        by_id[h.instrument_id] = h
        class_w[h.asset_class] = class_w.get(h.asset_class, 0.0) + ww
        if h.sector and h.sector not in ("broad", "mixed"):
            sector_w[h.sector] = sector_w.get(h.sector, 0.0) + ww
        if h.instrument_type in _ISSUER_TYPES and h.issuer:
            issuer_w[h.issuer] = issuer_w.get(h.issuer, 0.0) + ww
        if not h.fx_hedged and h.fx_ccy != profile.constraints.base_currency:
            fx_unhedged += ww
        is_liq = h.is_liquid if h.is_liquid is not None else h.asset_class not in _ILLIQUID_CLASSES
        if is_liq:
            liquid += ww

    cl = profile.concentration_limits
    cons = profile.constraints
    buf = profile.warn_buffer
    flags: list[SuitabilityFlag] = []

    plan_active = bool(profile.transition_bands and profile.transition_expiry
                       and as_of <= profile.transition_expiry)

    def _near_edge(cur: float, band: Bands) -> bool:
        near_min = band.min > 0.0 and cur <= band.min + buf
        near_max = band.max < 1.0 and cur >= band.max - buf
        return near_min or near_max

    # 1. Asset-class allocation bands (core suitability/drift check)
    for cls, sband in profile.allocation_bands.items():
        cur = class_w.get(cls, 0.0)
        eband = (profile.transition_bands or {}).get(cls, sband) if plan_active else sband
        if cur < eband.min or cur > eband.max:
            side = "below min" if cur < eband.min else "above max"
            flags.append(SuitabilityFlag(
                1, f"band:{cls}", "breach",
                f"{cls} {cur:.1%} {side} [{eband.min:.0%}-{eband.max:.0%}]"
                + (" (transition band)" if plan_active and eband is not sband else "")))
        elif plan_active and eband is not sband and (cur < sband.min or cur > sband.max):
            flags.append(SuitabilityFlag(
                1, f"band:{cls}", "on_plan",
                f"{cls} {cur:.1%} outside strategic [{sband.min:.0%}-{sband.max:.0%}] "
                f"but within transition plan (expires {profile.transition_expiry})"))
        elif _near_edge(cur, eband):
            flags.append(SuitabilityFlag(
                1, f"band:{cls}", "warn",
                f"{cls} {cur:.1%} near band edge [{eband.min:.0%}-{eband.max:.0%}]"))

    # 1b. Reciprocal check — a class HELD but with no band defined is not "clear",
    #     it is unconstrained. Flag it (else e.g. 40% unbanded alternatives reads OK).
    for cls, ww in class_w.items():
        if cls not in profile.allocation_bands:
            flags.append(SuitabilityFlag(
                1, f"unbanded:{cls}", "breach",
                f"{cls} {ww:.1%} held but has no allocation band defined in the profile"))

    # 2. Single-position concentration — different caps for funds vs single names;
    #    parked liquidity (cash / money-market) is exempt (covered by the cash band).
    for iid, ww in w.items():
        h = by_id[iid]
        if h.asset_class in _POSITION_CAP_EXEMPT_CLASSES or h.instrument_type in _POSITION_CAP_EXEMPT_TYPES:
            continue
        if h.instrument_type in _SINGLE_NAME:
            cap, kind = cl.max_single_security_pct, "single-security"
        else:
            cap, kind = cl.max_single_fund_pct, "fund"
        if ww > cap:
            flags.append(SuitabilityFlag(
                2, f"position:{iid}", "breach",
                f"{h.name} {ww:.1%} > {cap:.0%} {kind} cap"))
        elif cap > 0 and ww >= cap - buf:
            flags.append(SuitabilityFlag(
                2, f"position:{iid}", "warn",
                f"{h.name} {ww:.1%} near {cap:.0%} {kind} cap"))

    # 3. Single-issuer concentration (single names only; sovereigns exempt)
    for issuer, ww in issuer_w.items():
        if ww > cl.max_single_issuer_pct:
            flags.append(SuitabilityFlag(
                3, f"issuer:{issuer}", "breach",
                f"issuer {issuer} {ww:.1%} > {cl.max_single_issuer_pct:.0%} cap"))

    # 4. Sector concentration (funds tagged "broad"/"mixed" are invisible here —
    #    true look-through needs paid holdings data; tag thematic ETFs explicitly).
    for sector, ww in sector_w.items():
        if ww > cl.max_sector_pct:
            flags.append(SuitabilityFlag(
                4, f"sector:{sector}", "breach",
                f"sector {sector} {ww:.1%} > {cl.max_sector_pct:.0%} cap"))

    # 5a. Regulatory sanctioned instruments — HARD
    for iid, h in by_id.items():
        if iid in cons.sanctioned_instruments:
            flags.append(SuitabilityFlag(5, f"sanctioned:{iid}", "breach",
                                         f"{h.name}: sanctioned/prohibited instrument",
                                         hard=True))
    # 5b. Preference exclusions — mandate-driven (client may override their own list)
    for iid, h in by_id.items():
        why = None
        if h.asset_class in cons.excluded_asset_classes:
            why = f"asset class '{h.asset_class}' is on the client's exclusion list"
        elif h.sector and h.sector in cons.excluded_sectors:
            why = f"sector '{h.sector}' is on the client's exclusion list"
        elif iid in cons.excluded_instruments:
            why = "instrument is on the client's exclusion list"
        if why:
            flags.append(SuitabilityFlag(5, f"excluded:{iid}", "breach", f"{h.name}: {why}"))

    # 6. Unhedged FX exposure (economic, not denomination)
    if fx_unhedged > cons.max_unhedged_fx_pct:
        flags.append(SuitabilityFlag(
            6, "fx_exposure", "breach",
            f"unhedged non-{cons.base_currency} {fx_unhedged:.1%} > {cons.max_unhedged_fx_pct:.0%} cap"))
    elif cons.max_unhedged_fx_pct < 1.0 and fx_unhedged >= cons.max_unhedged_fx_pct - buf and fx_unhedged > 0:
        flags.append(SuitabilityFlag(
            6, "fx_exposure", "warn",
            f"unhedged FX {fx_unhedged:.1%} near {cons.max_unhedged_fx_pct:.0%} cap"))

    # 7. Liquidity floor
    if liquid < profile.min_liquid_pct:
        flags.append(SuitabilityFlag(
            7, "liquidity", "breach",
            f"liquid {liquid:.1%} < {profile.min_liquid_pct:.0%} minimum liquidity need"))

    # 8. Complex-product appropriateness — HARD (regulatory)
    if not profile.complex_products_ok:
        for iid, h in by_id.items():
            if h.is_complex:
                flags.append(SuitabilityFlag(
                    8, f"appropriateness:{iid}", "breach",
                    f"{h.name} is complex but the client is not cleared for complex products",
                    hard=True))

    if not flags:
        flags.append(SuitabilityFlag(0, "all_clear", "ok", "Book is within all suitability bands."))
    return _resolve_all(flags, profile.mandate)


# --------------------------------------------------------------------------- #
# Instruction diff — proposal vs the client's explicit instrument spec
# --------------------------------------------------------------------------- #

def instruction_diff(instructions: list[ClientInstruction], holdings: list[Holding],
                     mandate: str = "advisory", duration_tol: float = 0.5) -> list[SuitabilityFlag]:
    """Flag where a proposal deviates from what the client explicitly asked for:
    instrument CHARACTER (credit, duration, presence), the WEIGHT the client dictated,
    and the client's FEE screen ('low fees')."""
    flags: list[SuitabilityFlag] = []
    total = sum(h.market_value_base for h in holdings) or 1.0
    for instr in instructions:
        matched = [h for h in holdings
                   if h.asset_class == instr.asset_class
                   and (instr.instrument_type is None or h.instrument_type == instr.instrument_type)]
        if not matched:
            flags.append(SuitabilityFlag(
                10, f"unfilled:{instr.label}", "breach",
                f"no proposed instrument fulfils client instruction '{instr.label}'",
                domain="instruction"))
            continue

        # Weight fidelity — did the proposal honour the ratio the client dictated?
        if instr.target_weight is not None:
            got = sum(h.market_value_base for h in matched) / total
            if abs(got - instr.target_weight) > instr.weight_tol:
                flags.append(SuitabilityFlag(
                    13, f"weight:{instr.label}", "breach",
                    f"'{instr.label}': client set {instr.target_weight:.0%}, "
                    f"proposal is {got:.1%}", domain="instruction"))

        for h in matched:
            if (instr.credit and instr.credit != "any" and h.credit
                    and h.credit != instr.credit):
                flags.append(SuitabilityFlag(
                    11, f"credit:{h.instrument_id}", "breach",
                    f"'{instr.label}': client asked for {instr.credit}, "
                    f"{h.name} is {h.credit}", domain="instruction"))
            if (instr.max_duration_years is not None and h.effective_duration is not None
                    and h.effective_duration > instr.max_duration_years + duration_tol):
                flags.append(SuitabilityFlag(
                    12, f"duration:{h.instrument_id}", "breach",
                    f"'{instr.label}': client asked ≤{instr.max_duration_years}yr, "
                    f"{h.name} duration ≈{h.effective_duration}yr", domain="instruction"))
            # Fee screen — the client said "low fees and good liquidity".
            if (instr.max_expense_ratio is not None and h.expense_ratio is not None
                    and h.expense_ratio > instr.max_expense_ratio):
                flags.append(SuitabilityFlag(
                    14, f"fee:{h.instrument_id}", "breach",
                    f"'{instr.label}': fee screen ≤{instr.max_expense_ratio:.2f}%, "
                    f"{h.name} is {h.expense_ratio:.2f}%", domain="instruction"))
    if not flags:
        flags.append(SuitabilityFlag(10, "instructions_met", "ok",
                                     "Proposal matches all explicit client instructions.",
                                     domain="instruction"))
    return _resolve_all(flags, mandate)


def worst_enforcement(flags: list[SuitabilityFlag]) -> str:
    return max((f.enforcement for f in flags), key=lambda e: _ENFORCE_RANK[e], default="none")


def render(flags: list[SuitabilityFlag]) -> str:
    icon = {"block": "⛔", "flag": "⚑", "disclose": "ℹ", "none": "✓"}
    return "\n".join(f"  {icon.get(f.enforcement, '?')} [{f.enforcement:8}] "
                     f"rule {f.rule:>2} {f.name}: {f.detail}" for f in flags)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    bands = {
        "equity":       Bands(0.30, 0.65),
        "fixed_income": Bands(0.10, 0.40),
        "commodity":    Bands(0.00, 0.25),
        "cash":         Bands(0.05, 0.90),
    }

    # (A) Kadir's current book — cash is FIRST-CLASS now: $3M sitting in cash,
    #     nothing invested. No spurious single-position/0-floor noise.
    print("=== (A) Kadir now: $3M cash, execution_only ===")
    p = RiskProfile(mandate="execution_only", allocation_bands=bands)
    print(render(suitability_check(p, holdings=[], cash_balances={"USD": 3_000_000})))

    # (B) Same book, but a phased-entry TRANSITION PLAN is in force → the equity
    #     shortfall reads as 'on_plan', not a daily breach.
    print("\n=== (B) Same book, with a transition plan to end-2026 ===")
    p2 = RiskProfile(
        mandate="advisory", allocation_bands=bands,
        transition_bands={"equity": Bands(0.0, 0.65), "cash": Bands(0.05, 1.0)},
        transition_expiry=date(2026, 12, 31))
    print(render(suitability_check(p2, holdings=[], cash_balances={"USD": 3_000_000},
                                   as_of=date(2026, 7, 3))))

    # (C) Instruction diff — Kadir asked for a ~5yr *Treasury* bond sleeve at 20%,
    #     low-fee. The proposal: BND (mixed, ~5.7yr) + VCIT (corporate, ~6.1yr),
    #     over-weighted, with a hypothetical pricey share class to show the fee screen.
    print("\n=== (C) Instruction diff: character + weight + fee ===")
    instr = [ClientInstruction("bond sleeve", "fixed_income", credit="treasury",
                               max_duration_years=5.0, target_weight=0.20,
                               max_expense_ratio=0.10)]
    proposal = [
        Holding("BND", "Vanguard Total Bond Market ETF", "bond_etf", "fixed_income",
                600_000, effective_duration=5.7, credit="mixed", expense_ratio=0.03),
        Holding("VCITX", "a pricey active corp-bond fund", "bond_etf", "fixed_income",
                600_000, effective_duration=6.1, credit="corporate", expense_ratio=0.42),
    ]  # 1.2m of a 1.2m book => 100% vs the client's 20% target
    print(render(instruction_diff(instr, proposal, mandate="advisory")))

    # (D) Reciprocal band check — a book holding an unbanded asset class.
    print("\n=== (D) Held class with no band defined ===")
    p4 = RiskProfile(mandate="discretionary", allocation_bands=bands)
    alts = [Holding("PE1", "Private equity fund", "alternative", "alternatives",
                    1_200_000, is_liquid=False)]
    print(render(suitability_check(p4, holdings=alts, cash_balances={"USD": 1_800_000})))
