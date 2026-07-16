"""Macro overlays — a client macro view MOVES the recommendation, deterministically.

Each overlay is a fixed, bounded tilt of the target allocation. The rebalancer chases
the tilted target, so asserting the tilt's DIRECTION is asserting the direction the
recommendation shifts (more/less buying of a sleeve). These tests lock the direction of
every scenario, plus the invariants that keep it honest: tilts sum to zero (the book
stays fully invested), nothing goes negative, and 'none' changes nothing.
"""
from __future__ import annotations

import pytest

import macro_overlay as mo

# The built-in Balanced strategic target (percent), by asset class.
BASE = {"equity": 50.0, "fixed_income": 30.0, "commodity": 10.0, "cash": 10.0,
        "fx": 0.0, "structured_products": 0.0}

# scenario -> {sleeve: expected direction}  (+1 up, -1 down)
DIRECTIONS = {
    "rate_cuts":  {"fixed_income": +1, "cash": -1},               # deploy cash into bonds
    "rate_hikes": {"fixed_income": -1, "cash": +1},               # shorten, raise cash
    "defensive":  {"equity": -1, "commodity": +1, "cash": +1},    # risk-off: gold+cash up, equity down
    "risk_on":    {"equity": +1, "commodity": -1, "cash": -1},    # risk-on: equity up
    "tax_aware":  {"equity": -1, "commodity": +1},                # trim US-situs into non-US-situs gold
}


@pytest.mark.parametrize("key,dirs", DIRECTIONS.items())
def test_overlay_moves_each_sleeve_the_right_way(key, dirs):
    tilted, ov = mo.apply_overlay(BASE, key)
    for sleeve, direction in dirs.items():
        delta = tilted[sleeve] - BASE[sleeve]
        assert (delta > 0) if direction > 0 else (delta < 0), (
            f"{key}: expected {sleeve} to move "
            f"{'up' if direction > 0 else 'down'}, got {BASE[sleeve]}→{tilted[sleeve]}")


@pytest.mark.parametrize("key", DIRECTIONS)
def test_overlay_preserves_total_allocation(key):
    tilted, _ = mo.apply_overlay(BASE, key)
    assert round(sum(tilted.values()), 6) == round(sum(BASE.values()), 6), \
        "a tilt must sum to zero — the book stays fully invested"


@pytest.mark.parametrize("key", DIRECTIONS)
def test_overlay_never_goes_negative(key):
    tilted, _ = mo.apply_overlay(BASE, key)
    assert all(v >= 0 for v in tilted.values())


def test_none_overlay_is_a_no_op():
    tilted, ov = mo.apply_overlay(BASE, "none")
    assert tilted == BASE and ov.key == "none"
    assert mo.changes(BASE, "none") == []
    assert mo.describe(BASE, "none") == ""


def test_unknown_overlay_falls_back_to_none():
    tilted, ov = mo.apply_overlay(BASE, "does_not_exist")
    assert tilted == BASE and ov.key == "none"


@pytest.mark.parametrize("key", DIRECTIONS)
def test_changes_reports_only_moved_sleeves_and_describe_is_provenanced(key):
    ch = mo.changes(BASE, key)
    assert ch, f"{key}: expected reported changes"
    moved = {lbl for lbl, _, _ in ch}
    # every reported row genuinely moved
    for lbl, b, t in ch:
        assert abs(t - b) > 1e-6
    # the one-line description names the overlay and carries a rationale (provenance)
    desc = mo.describe(BASE, key)
    assert mo.OVERLAYS[key].label in desc
    assert "deterministic" in desc.lower()


def test_overlay_stays_within_a_wide_policy_band():
    """Tilts are modest: no sleeve moves more than 8pp from its strategic target, so a
    tilt never breaches a normal ±15% suitability band on its own."""
    for key in DIRECTIONS:
        tilted, _ = mo.apply_overlay(BASE, key)
        assert all(abs(tilted[k] - BASE[k]) <= 8.0 + 1e-6 for k in BASE)


def test_clamped_tilt_still_sums_correctly():
    """If a tilt would drive a sleeve negative, it clamps at 0 and renormalises so the
    total is preserved (no phantom allocation)."""
    tiny = {"equity": 90.0, "fixed_income": 2.0, "commodity": 3.0, "cash": 5.0,
            "fx": 0.0, "structured_products": 0.0}
    tilted, _ = mo.apply_overlay(tiny, "rate_hikes")   # fixed_income -6 would go negative
    assert all(v >= 0 for v in tilted.values())
    assert round(sum(tilted.values()), 6) == round(sum(tiny.values()), 6)
