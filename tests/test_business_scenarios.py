"""Business scenarios — what happens to the OUTPUT when the client voices a macro
view: a rate hike/cut, a war (or its end) driving a request for alternatives, or a
tax increase/decrease. These are the questions a private banker actually asks.

The product's contract, which these tests pin down:
  1. the scenario reaches the AI verbatim (it's in the prompt),
  2. it SHAPES the advisory commentary (the write-up reflects it),
  3. it does NOT move the computed figures — every number stays grounded in the
     holdings + mandate; a macro opinion never invents or alters a number,
  4. for interest rates, the deterministic rate tool reports the bond exposure and
     refuses to fabricate a sensitivity it cannot source.

A client who wants the macro view to actually re-weight the book does that by
changing the intake targets (or a future macro-overlay) — not by opinion alone.
"""
from __future__ import annotations

import pytest

import narrative
import portfolio_qa as pq
from conftest import make_model


# Realistic client statements, by scenario. (id, text, keyword-that-must-survive)
SCENARIOS = [
    ("rate_hike", "I expect the US Federal Reserve to HIKE interest rates further "
                  "this year — keep the bond sleeve short.", "hike"),
    ("rate_cut", "I expect interest rates to be LOWERED over the coming quarters — "
                 "consider extending duration.", "lower"),
    ("war_shock", "Given the current war and market turmoil, I want more defensive, "
                  "alternative recommendations.", "defensive"),
    ("war_end", "With the US-Iran war ending, I'm comfortable adding risk-on "
                "exposure again.", "us-iran"),
    ("tax_hike", "The US government is imposing further taxes — please factor in "
                 "tax efficiency.", "tax"),
    ("tax_cut", "US tax cuts are coming — revisit the after-tax positioning of the "
                "book.", "tax"),
]

CHANNELS = ["tactical", "document"]   # the two ways a client voices this

BASELINE = make_model(with_docs=False, tactical=None)   # no macro view at all


def _model(text: str, channel: str) -> dict:
    """A proposal model carrying the scenario as either a tactical instruction or an
    'other document' (e.g. a client email) — the two real ingestion paths."""
    m = make_model(with_docs=False, tactical=None)
    if channel == "tactical":
        m["tactical_text"] = text
    else:
        doc = {"name": "Client_View.eml", "text": text, "ok": True, "chars": len(text)}
        m["other_docs"] = [doc]
        m["reference_docs"] = [doc]
    return m


# --- 1. the scenario reaches the AI verbatim -------------------------------- #
@pytest.mark.parametrize("sid,text,kw", SCENARIOS, ids=[s[0] for s in SCENARIOS])
@pytest.mark.parametrize("channel", CHANNELS)
def test_scenario_reaches_the_prompt(sid, text, kw, channel):
    m = _model(text, channel)
    assert text in narrative.build_commentary_prompt(m), \
        f"{sid}/{channel}: scenario missing from the commentary prompt"
    assert text in narrative.build_prompt(m), \
        f"{sid}/{channel}: scenario missing from the portable deck prompt"


# --- 2. the scenario SHAPES the advisory commentary ------------------------- #
@pytest.mark.parametrize("sid,text,kw", SCENARIOS, ids=[s[0] for s in SCENARIOS])
@pytest.mark.parametrize("channel", CHANNELS)
def test_scenario_shapes_the_commentary(sid, text, kw, channel):
    m = _model(text, channel)
    commentary = narrative.deterministic_summary(m)
    assert kw in commentary.lower(), \
        f"{sid}/{channel}: commentary does not reflect the scenario ({kw!r})"
    # and it genuinely CHANGED the write-up vs. no macro view
    assert commentary != narrative.deterministic_summary(BASELINE)


# --- 3. the scenario does NOT change the numbers ---------------------------- #
@pytest.mark.parametrize("sid,text,kw", SCENARIOS, ids=[s[0] for s in SCENARIOS])
@pytest.mark.parametrize("channel", CHANNELS)
def test_scenario_leaves_the_numbers_grounded(sid, text, kw, channel):
    """A macro opinion shapes prose, never figures: the FACTS block (every number
    the deck shows) is byte-for-byte identical with and without the scenario."""
    m = _model(text, channel)
    assert narrative.facts_block(m) == narrative.facts_block(BASELINE), \
        f"{sid}/{channel}: a macro view must not alter the computed figures"


# --- 4. interest rates: the engine reports exposure, never invents impact ---- #
def test_rate_scenario_reports_exposure_without_fabricating(book):
    """'What if rates are hiked?' → the deterministic tool states the fixed-income
    exposure but refuses to estimate a +100bp impact it cannot source."""
    ans = pq.t_rate_scenario(book)
    assert "fixed-income" in ans.summary.lower() or "bond" in ans.summary.lower()
    # a dollar exposure is reported ...
    assert any("$" in str(v) for _, v, _ in ans.facts)
    # ... but no sensitivity figure is fabricated where duration isn't sourced
    honest = ("not sourced" in ans.summary.lower()
              or "won't estimate" in ans.summary.lower()
              or any("SOURCE REQUIRED" in str(src) for *_, src in ans.facts))
    assert honest, "rate tool must not invent an unsourced sensitivity"


def test_rate_question_routes_to_the_rate_tool(book):
    for q in ("what if the Fed hikes interest rates?",
              "impact of a +100bp rate move?",
              "how exposed are we if rates are lowered?"):
        ans = pq.ask(book, q)
        assert "rate" in ans.tool.lower() or "fixed-income" in ans.summary.lower()


# --- 5. end-to-end: the deck's PROSE moves, its TABLES don't ---------------- #
def test_scenario_changes_deck_prose_not_its_numbers():
    import generate_proposal as gp
    war = _model("Given the war, shift toward defensive, alternative positions.", "tactical")
    base = make_model(with_docs=False, tactical=None)
    for m in (war, base):
        m["narrative"] = narrative.deterministic_summary(m)
    war_html, base_html = gp.render_html(war), gp.render_html(base)
    # the commentary (prose) differs ...
    assert war_html != base_html
    assert "defensive" in war_html.lower()
    # ... while the headline figures are present and identical in both
    for figure in ("$4,919,914", "$5,819,914"):
        assert figure in war_html and figure in base_html
