"""macro_overlay.py — deterministic macro overlays for the proposal engine.

A client macro VIEW (rates, geopolitics, tax) should move the RECOMMENDATION, not
just the write-up. This module does that deterministically: each named scenario maps
to a **fixed, bounded tilt** of the target allocation — a documented rule table, never
a model-invented number. The tilts sum to zero (the book stays fully invested) and are
clamped at zero. The rebalancer then chases the tilted target, so the trades shift in
the scenario's direction, while every figure stays deterministic and carries provenance
(the overlay key, the exact tilt, and a rationale travel with the proposal).

Targets are keyed by ASSET CLASS (equity, fixed_income, commodity, cash, fx,
structured_products) — the same keys app.py uses. In the built-in book: gold →
commodity, money-market → cash, Nasdaq-100 / S&P 500 → equity, bonds → fixed_income.

Advisory and reversible: overlays are a tactical tilt WITHIN the strategic policy; the
suitability bands stay on the base target (an overlay never relaxes a guardrail).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Overlay:
    key: str
    label: str
    tilts: dict            # asset-class -> delta in percentage points (sum to 0)
    rationale: str = ""
    implementation: str = ""   # duration / wrapper note for the write-up


# The rule table. Tilts are percentage-point deltas on the target allocation and sum
# to zero. Magnitudes are deliberately modest (a tactical tilt, not a regime change).
OVERLAYS: dict[str, Overlay] = {
    "none": Overlay("none", "No macro overlay", {},
                    "No macro view applied — the strategic target stands."),
    "rate_cuts": Overlay(
        "rate_cuts", "Rate cuts expected",
        {"fixed_income": +6, "cash": -6},
        "Falling policy rates: reinvestment risk outweighs price risk — deploy parked "
        "cash into bonds.",
        "Extend the bond sleeve toward medium duration; build in tranches."),
    "rate_hikes": Overlay(
        "rate_hikes", "Rate hikes expected",
        {"fixed_income": -6, "cash": +6},
        "Rising policy rates: reduce duration and hold dry powder until the cycle turns.",
        "Keep the bond sleeve short; park liquidity in the money-market fund."),
    "defensive": Overlay(
        "defensive", "Geopolitical risk-off",
        {"equity": -8, "commodity": +5, "cash": +3},
        "Conflict / market turmoil: reduce risk assets, raise gold and dry powder.",
        "Defer discretionary equity adds; lean on gold as a safe haven."),
    "risk_on": Overlay(
        "risk_on", "Risk-on / de-escalation",
        {"equity": +8, "commodity": -5, "cash": -3},
        "De-escalation: rotate from safe havens back into risk assets.",
        "Re-engage US equity; run down excess cash and defensive gold."),
    "tax_aware": Overlay(
        "tax_aware", "US tax drag (non-US person)",
        {"equity": -4, "commodity": +4},
        "Higher US withholding / estate drag on US-situs assets: trim US-equity "
        "concentration at the margin toward non-US-situs holdings.",
        "Prefer accumulating / non-US-domiciled (Irish UCITS) wrappers for US equity; "
        "route new money there rather than triggering gains."),
}

# Labels for asset-class keys, for the write-up / banners.
CLASS_LABEL = {"equity": "Equity", "fixed_income": "Fixed income", "commodity": "Commodity",
               "cash": "Cash", "fx": "FX", "structured_products": "Structured products"}


def options() -> list[tuple[str, str]]:
    """(key, label) pairs for a UI selector, 'none' first."""
    return [(o.key, o.label) for o in OVERLAYS.values()]


def apply_overlay(target_all: dict, key: str | None) -> tuple[dict, Overlay]:
    """Return (tilted_target, overlay). Tilts are applied to the base target, clamped
    at zero, then renormalised to the base total so the allocation stays fully invested
    (the sum is preserved). 'none'/unknown returns the base target unchanged."""
    ov = OVERLAYS.get(key or "none", OVERLAYS["none"])
    base = {k: float(v) for k, v in target_all.items()}
    if not ov.tilts:
        return base, ov
    out = dict(base)
    for sleeve, delta in ov.tilts.items():
        if sleeve in out:                     # only tilt sleeves the client actually uses
            out[sleeve] = max(0.0, out[sleeve] + float(delta))
    tot0, tot1 = sum(base.values()), sum(out.values())
    if tot1 > 0 and tot0 > 0 and abs(tot1 - tot0) > 1e-9:   # renormalise only if clamping moved the sum
        out = {k: v * tot0 / tot1 for k, v in out.items()}
    return out, ov


def changes(target_all: dict, key: str | None) -> list[tuple[str, float, float]]:
    """(class-label, base_pct, tilted_pct) for each sleeve the overlay actually moved —
    for the deck banner, the prompt and the provenance trail."""
    tilted, ov = apply_overlay(target_all, key)
    rows = []
    for sleeve in target_all:
        b, t = float(target_all[sleeve]), float(tilted[sleeve])
        if abs(t - b) > 1e-6:
            rows.append((CLASS_LABEL.get(sleeve, sleeve.replace("_", " ").title()), b, t))
    return rows


def describe(target_all: dict, key: str | None) -> str:
    """One-line, provenance-friendly summary of the applied overlay (or '' for none)."""
    tilted, ov = apply_overlay(target_all, key)
    ch = changes(target_all, key)
    if not ch:
        return ""
    moves = "; ".join(f"{lbl} {b:.0f}%→{t:.0f}%" for lbl, b, t in ch)
    return (f"Macro overlay — {ov.label}: {moves}. {ov.rationale} "
            f"({ov.implementation}) Tactical tilt within the strategic policy; "
            f"figures remain deterministic.")
