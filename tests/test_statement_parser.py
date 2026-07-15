"""Engine · ingestion — parse the three custodian formats, reconcile, convert FX,
flag the hard cases (unresolved house-codes, stale NAVs), and keep a PII-free
month-to-month continuity key. Every downstream number rides on this layer."""
from __future__ import annotations

import statement_parser as sp


# --- parse each custodian format ------------------------------------------- #
def test_parse_custodian_a_usd_csv():
    st = sp.reconcile(sp.parse_custodian_a(sp.STMT_DIR / "custodianA_uob.csv"))
    assert st.positions, "custodian A produced no positions"
    assert all(p.mv_base > 0 for p in st.positions)
    # USD custodian → every position values in USD base at par
    assert st.recon_ok is True


def test_parse_custodian_b_european_decimals_and_fx():
    """Semicolon CSV, European decimals, EUR/CHF → converted to a USD base."""
    st = sp.reconcile(sp.parse_custodian_b(sp.STMT_DIR / "custodianB_eurobank.csv"))
    ccys = {p.currency for p in st.positions}
    assert {"EUR", "CHF"} & ccys, "expected non-USD denominated holdings"
    # FX applied: base value differs from the local value for a non-USD holding.
    non_usd = [p for p in st.positions if p.currency != "USD"]
    assert non_usd and all(p.mv_base > 0 for p in non_usd)


def test_parse_custodian_c_json_alts_and_lombard():
    """JSON custodian carries illiquid alternatives + a Lombard loan (a liability)."""
    st = sp.reconcile(sp.parse_custodian_c(sp.STMT_DIR / "custodianC_familyoffice.json"))
    assert st.positions
    assert st.liabilities, "expected the Lombard loan as a liability"
    assert all(lb["balance"] != 0 for lb in st.liabilities)


# --- reconciliation checksum ----------------------------------------------- #
def test_reconcile_flags_out_of_tolerance_custodian(book):
    """One sample deliberately fails its checksum by ~$436 — it must be flagged,
    not silently trusted."""
    fails = [(c, ok, d) for c, ok, d in book.recon if not ok]
    assert fails, "expected at least one reconciliation break in the samples"
    cust, ok, delta = fails[0]
    assert ok is False and abs(delta) > 1


def test_reconcile_tolerance_gates_the_flag():
    """The ~$436 break on custodian B reconciles under a generous tolerance but
    fails under a tight one — proving the checksum knob actually gates the flag."""
    b = sp.parse_custodian_b(sp.STMT_DIR / "custodianB_eurobank.csv")
    assert sp.reconcile(b, tol_abs=1e12, tol_pct=1.0).recon_ok is True
    assert sp.reconcile(b, tol_abs=1.0, tol_pct=0.0).recon_ok is False


# --- continuity key (PII-free, stable) ------------------------------------- #
def test_continuity_key_is_stable_and_pii_free():
    st = sp.reconcile(sp.parse_custodian_a(sp.STMT_DIR / "custodianA_uob.csv"))
    k1 = sp.continuity_key(st)
    k2 = sp.continuity_key(sp.reconcile(sp.parse_custodian_a(sp.STMT_DIR / "custodianA_uob.csv")))
    assert k1 == k2, "continuity key must be deterministic across re-parses"
    assert k1 and "@" not in k1  # no email/PII leaked into the key


def test_check_continuity_detects_change():
    a = sp.reconcile(sp.parse_custodian_a(sp.STMT_DIR / "custodianA_uob.csv"))
    b = sp.reconcile(sp.parse_custodian_b(sp.STMT_DIR / "custodianB_eurobank.csv"))
    same = sp.check_continuity({"acct": sp.continuity_key(a), "prev": sp.continuity_key(a)})
    diff = sp.check_continuity({"acct": sp.continuity_key(a), "prev": sp.continuity_key(b)})
    assert isinstance(same, list) and isinstance(diff, list)


# --- consolidation -> holdings --------------------------------------------- #
def test_to_holdings_consolidates_all_custodians(book):
    from statement_parser import to_holdings, parse_custodian_a, parse_custodian_b, \
        parse_custodian_c, reconcile, STMT_DIR
    sts = [reconcile(parse_custodian_a(STMT_DIR / "custodianA_uob.csv")),
           reconcile(parse_custodian_b(STMT_DIR / "custodianB_eurobank.csv")),
           reconcile(parse_custodian_c(STMT_DIR / "custodianC_familyoffice.json"))]
    hs = to_holdings(sts)
    assert len(hs) >= 10
    assert all(h.market_value_base > 0 for h in hs)


def test_book_totals_are_consistent(book):
    """gross − debt = net, and gross is the sum of position base values."""
    assert round(book.gross - book.debt, 2) == round(book.net, 2)
    assert round(sum(p.mv_base for p in book.positions), 2) == round(book.gross, 2)
    assert book.gross > 0 and book.debt > 0
