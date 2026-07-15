"""Shared fixtures for the Meridian Family Office Copilot test-suite.

The suite exercises the platform at three levels:
  1. the deterministic ENGINE (parser / suitability / Q&A)   — pure, no Streamlit
  2. the DELIVERABLE layer (prompt + narrative + deck render) — pure, no Streamlit
  3. the APP end-to-end (Streamlit AppTest, DEMO_MODE)         — see test_app_scenarios

Everything runs offline in DEMO_MODE — no API key, no network, no billing.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# Force the keyless demo path for every test (deterministic, offline).
os.environ.setdefault("DEMO_MODE", "1")

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Engine-level fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def book():
    """The consolidated, reconciled book from the three built-in custodian samples."""
    import portfolio_qa as pq
    return pq.load_book()


@pytest.fixture(scope="session")
def sample_dir():
    import statement_parser as sp
    return sp.STMT_DIR


# --------------------------------------------------------------------------- #
# Deliverable-level fixture — a COMPLETE deck model matching app.proposal_model's
# output shape, so narrative.py + generate_proposal.py can be tested without
# Streamlit. `with_docs` toggles the research/other documents + tactical text.
# --------------------------------------------------------------------------- #
def make_model(with_docs: bool = False,
               mandate: str = "Advisory",
               tactical: str | None = "Gold below USD 4,000/oz; buy bonds in tranches; "
                                      "add US equity only after a 15-20% pullback.") -> dict:
    notes = ["Money market: held as dry powder pending a 15-20% US-equity pullback."]
    tac = (tactical or "").strip()
    if tac:
        notes.append("Client tactical instructions (verbatim, folded in as guidance, "
                     f"NOT a source of figures): {tac}")
    research, other = [], []
    if with_docs:
        research = [{"name": "CIO_Outlook.md",
                     "text": "House view: range-bound US equity into year-end; favour "
                             "medium-duration government bonds; stay patient on gold.",
                     "ok": True, "chars": 120}]
        other = [{"name": "Client_Email_Kadir.pdf",
                  "text": "I expect a liquidity event in Q4 - a property sale that should "
                          "free up roughly USD 500k of additional cash to invest. Please "
                          "keep dry powder in mind.", "ok": True, "chars": 150}]
        for d in research + other:
            notes.append(f"Document “{d['name']}” read and folded in as advisory "
                         f"context ({d['chars']:,} chars; NOT a source of figures).")

    return {
        "title": "Asset Allocation Proposal",
        "subtitle": "Consolidated Portfolio · $4,919,914 net worth",
        "as_of": "2026-07-02", "prov": "deterministic engine v10",
        "meta": {"custodians": 3, "entities": 3, "positions": 12,
                 "mandate": mandate, "risk": "Moderate", "ability": "Solid"},
        "custodian_list": ["Alpine Trust Services (SPV)", "Banque Privée", "UOB Private Bank"],
        "metrics": [("Net worth", "$4,919,914"), ("Gross assets", "$5,819,914"),
                    ("Liabilities", "$900,000"), ("Leverage (debt/net)", "18.3%"),
                    ("Liquid assets", "26.1%")],
        "gross_str": "$5,819,914",
        "alloc_rows": [["Equity", "$500,000", "8.6%", "30.0%", "-21.4 pp"],
                       ["Fixed Income", "$360,000", "6.2%", "10.0%", "-3.8 pp"]],
        "reb_rows": [["Equity", "8.6%", "30.0%", "+1,245,000", "buy", "below band"],
                     ["Fixed Income", "6.2%", "10.0%", "+220,000", "buy", "below band"]],
        "reb_summary": {"buys": "$1,465,000", "sells": "$0", "net": "$+1,465,000",
                        "selffund": False},
        "gate": "flag",
        "suit_items": [("flag", "rule 1 · equity 8.6% below min [30%-65%]")],
        "data_quality": [("Reconciliation", "Banque Privée: parsed vs stated differ by $436.40")],
        "analyst_notes": notes, "overlays": [],
        "intake": {"mandate": mandate, "risk": "Moderate", "ability": "Solid",
                   "objective": "Balanced growth", "horizon": "10+ yrs", "baseccy": "USD",
                   "complex": "No", "usperson": "No",
                   "target_all": {"money_market": 10, "gold": 20, "fixed_income": 20,
                                  "nasdaq100": 20, "sp500": 30},
                   "tol": 5, "minliq": 10, "maxfx": 30, "maxpos": 10,
                   "excl": {"alternatives": False, "real_estate": False, "commodity": False}},
        "holdings": [{"name": "S&P 500 ETF", "asset_class": "equity", "currency": "USD",
                      "mv_base": 500000, "custodian": "UOB Private Bank"}],
        "statement_sources": [{"name": "custodianA_uob.csv",
                               "text": "name,asset_class,value\nS&P 500 ETF,equity,500000"}],
        "research_docs": research, "other_docs": other, "tactical_text": tac,
        "reference_docs": [d for d in research + other if d.get("ok")],
    }


@pytest.fixture
def deck_model():
    """Factory: deck_model(with_docs=..., mandate=..., tactical=...)."""
    return make_model
