"""Engine · suitability — the deterministic policy checks. The mandate decides
what a breach MEANS (execution_only→disclose, advisory→flag, discretionary→block),
plus concentration, liquidity, unhedged-FX, complex-product and sanctions rules,
and the instruction-diff that catches "BND vs the client's 5-yr Treasury" drift."""
from __future__ import annotations

import suitability_check as sc
from suitability_check import (Bands, Constraints, Holding, RiskProfile,
                               ClientInstruction, instruction_diff,
                               suitability_check, worst_enforcement)


def _profile(mandate="advisory", **kw):
    return RiskProfile(mandate=mandate,
                       allocation_bands={"equity": Bands(0.30, 0.65),
                                         "fixed_income": Bands(0.10, 0.40),
                                         "cash": Bands(0.05, 0.90)},
                       min_liquid_pct=kw.pop("min_liquid_pct", 0.10), **kw)


def _equity(mv, **kw):
    return Holding("EQ", "Equity ETF", "equity_etf", "equity", mv, **kw)


# --- mandate semantics: the SAME breach means different things --------------- #
def test_mandate_maps_breach_to_enforcement():
    """A single overweight equity book, evaluated under each mandate, yields the
    mandate-appropriate enforcement on the band breach."""
    book = [_equity(1_000_000)]  # 100% equity → above the 65% band, below no min
    seen = {}
    for mandate in ("execution_only", "advisory", "discretionary"):
        flags = suitability_check(_profile(mandate), book)
        seen[mandate] = worst_enforcement(flags)
    assert seen["execution_only"] == "disclose"
    assert seen["advisory"] == "flag"
    assert seen["discretionary"] == "block"


def test_within_bands_is_clean():
    """A balanced book inside every band produces no actionable breach."""
    book = [Holding("SPY", "S&P 500 ETF", "equity_etf", "equity", 250_000),
            Holding("EFA", "Intl Equity ETF", "equity_etf", "equity", 250_000),
            Holding("FI", "Bond ETF", "bond_etf", "fixed_income", 250_000),
            Holding("MM", "USD MMF", "money_market", "cash", 250_000)]
    flags = suitability_check(_profile("advisory"), book)
    assert worst_enforcement(flags) in ("none", "disclose")


# --- concentration ---------------------------------------------------------- #
def test_single_security_concentration_flagged():
    """A single stock above the 10% single-security cap is caught; a diversified
    fund of the same weight is not."""
    stock = [Holding("AAPL", "Apple", "single_stock", "equity", 300_000,
                     issuer="Apple", sector="tech"),
             _equity(700_000)]
    flags = suitability_check(_profile("advisory"), stock)
    assert any("concentr" in f.name.lower() or "position" in f.name.lower()
               or "issuer" in f.name.lower() for f in flags
               if f.enforcement != "none")


def test_money_market_exempt_from_position_cap():
    """Parked liquidity (money-market) is exempt from the single-position cap."""
    book = [Holding("MM", "USD MMF", "money_market", "cash", 900_000),
            _equity(100_000)]
    flags = suitability_check(_profile("advisory"), book)
    # no position/concentration block should be raised on the money-market sleeve
    assert not any(f.enforcement == "block" and "MMF" in f.detail for f in flags)


# --- liquidity floor -------------------------------------------------------- #
def test_liquidity_floor_breach():
    """Below the min-liquid floor (here mostly illiquid alternatives) is flagged."""
    book = [Holding("ALT", "PE Fund", "alternative", "alternatives", 900_000,
                    is_liquid=False),
            _equity(100_000)]
    flags = suitability_check(_profile("advisory", min_liquid_pct=0.30), book)
    assert any("liquid" in f.name.lower() for f in flags if f.enforcement != "none")


# --- unhedged FX ------------------------------------------------------------ #
def test_unhedged_fx_breach():
    """Economic FX exposure above the max-unhedged cap is flagged."""
    prof = _profile("advisory")
    prof.constraints.max_unhedged_fx_pct = 0.10
    book = [_equity(600_000, currency="EUR", exposure_currency="EUR", fx_hedged=False),
            _equity(400_000)]
    flags = suitability_check(prof, book)
    assert any("fx" in f.name.lower() or "currency" in f.name.lower()
               for f in flags if f.enforcement != "none")


# --- hard regulatory rules apply under EVERY mandate ------------------------ #
def test_sanctioned_instrument_hard_blocks_even_execution_only():
    prof = _profile("execution_only")
    prof.constraints.sanctioned_instruments = ["BADCO"]
    book = [Holding("BADCO", "Sanctioned Co", "single_stock", "equity", 100_000,
                    issuer="BADCO"), _equity(900_000)]
    flags = suitability_check(prof, book)
    hard = [f for f in flags if f.hard]
    assert hard and any(f.enforcement == "block" for f in hard)


def test_complex_product_appropriateness_blocks_when_not_allowed():
    prof = _profile("advisory", complex_products_ok=False)
    book = [Holding("SP", "Autocallable Note", "structured_product", "structured_products",
                    200_000, is_complex=True), _equity(800_000)]
    flags = suitability_check(prof, book)
    assert any(f.enforcement == "block" for f in flags)


# --- instruction diff: the BND-vs-"5yr Treasury" defect --------------------- #
def test_instruction_diff_catches_wrong_instrument():
    """Client asked for a treasury sleeve; the proposal holds a corporate-credit
    bond fund of the wrong duration → a deviation flag."""
    instr = [ClientInstruction("bond sleeve", "fixed_income", credit="treasury",
                               max_duration_years=5.0)]
    proposal = [Holding("LQD", "Corp Bond ETF", "bond_etf", "fixed_income", 300_000,
                        credit="corporate", effective_duration=8.5)]
    flags = instruction_diff(instr, proposal, mandate="advisory")
    assert flags, "expected an instruction-deviation flag"
    assert any(f.enforcement != "none" for f in flags)


def test_instruction_diff_satisfied_when_matched():
    instr = [ClientInstruction("bond sleeve", "fixed_income", credit="treasury",
                               max_duration_years=5.0)]
    proposal = [Holding("UST5", "5yr Treasury ETF", "bond_etf", "fixed_income", 300_000,
                        credit="treasury", effective_duration=4.6)]
    flags = instruction_diff(instr, proposal, mandate="advisory")
    assert all(f.enforcement == "none" for f in flags) or not flags


# --- worst_enforcement ranking ---------------------------------------------- #
def test_worst_enforcement_ranking():
    mk = lambda e: sc.SuitabilityFlag(1, "n", "warn", "d", enforcement=e)
    assert worst_enforcement([mk("none"), mk("disclose"), mk("flag")]) == "flag"
    assert worst_enforcement([mk("flag"), mk("block")]) == "block"
    assert worst_enforcement([]) == "none"


# --- the real consolidated book -------------------------------------------- #
def test_real_book_gate_is_flag_under_advisory(book):
    """The three-custodian sample book, under its advisory profile, lands on a
    'flag' gate (bands breached, nothing hard-blocked)."""
    assert worst_enforcement(book.suit) == "flag"
