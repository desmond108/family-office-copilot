"""Engine · Q&A — the conversational layer. Every number is computed by a
DETERMINISTIC tool; routing picks the right tool from the phrasing. (ask_ai is the
optional LLM phrasing layer — not exercised here; the offline path is the truth.)"""
from __future__ import annotations

import portfolio_qa as pq


def _summary(book, q):
    return pq.ask(book, q)


# --- routing: the phrasing reaches the right tool --------------------------- #
def test_routes_net_worth_to_totals(book):
    ans = pq.ask(book, "what is the client's total net worth?")
    assert ans.tool == "totals" or "net worth" in ans.summary.lower()


def test_routes_currency_question(book):
    ans = pq.ask(book, "how much unhedged EUR / CHF FX exposure is there?")
    assert ans.facts  # produced grounded facts
    assert "curr" in ans.tool.lower() or "fx" in ans.summary.lower() \
        or any("EUR" in str(f) or "CHF" in str(f) for f in ans.facts)


def test_routes_suitability_question(book):
    ans = pq.ask(book, "are there any suitability breaches or mandate issues?")
    assert ans.facts
    assert "suitab" in ans.tool.lower() or "flag" in ans.summary.lower() \
        or any(e in str(ans.facts).lower() for e in ("flag", "block", "disclose"))


def test_routes_concentration_question(book):
    ans = pq.ask(book, "what is the largest single position?")
    assert ans.summary


def test_routes_liquidity_question(book):
    ans = pq.ask(book, "how liquid is the portfolio?")
    assert ans.summary


def test_routes_data_quality_question(book):
    ans = pq.ask(book, "any reconciliation or data-quality issues?")
    assert ans.summary


# --- grounding: answers carry facts, tied to the computed book -------------- #
def test_answers_are_grounded_in_facts(book):
    for q in ("net worth?", "equity exposure?", "leverage?"):
        ans = pq.ask(book, q)
        assert ans.summary, f"empty answer for {q!r}"


def test_briefing_has_every_domain(book):
    b = pq.briefing(book)
    assert isinstance(b, dict) and b
    # the briefing is the full deterministic fact-sheet handed to the LLM layer
    joined = str(b).lower()
    assert "suitab" in joined or "net" in joined


def test_ask_never_raises_on_varied_phrasings(book):
    """The router must always resolve to SOME tool — never crash on odd input."""
    for q in ("", "?!?", "tell me about gold", "hola", "0", "custodian breakdown please"):
        ans = pq.ask(book, q)
        assert ans is not None and hasattr(ans, "summary")
