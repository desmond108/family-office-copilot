"""Deliverable · deck render — HTML / PPTX / PDF renderers agree, every figure is
copied from the model, and the CIO commentary (when present) folds in as a slide.
This is where the v10 fix lands: with documents, the exported deck changes."""
from __future__ import annotations

import narrative
import generate_proposal as gp
from conftest import make_model


def _with_narrative(with_docs):
    m = make_model(with_docs=with_docs)
    m["narrative"] = narrative.deterministic_summary(m)
    return m


# --- all three renderers produce output ------------------------------------- #
def test_renderers_produce_output():
    m = _with_narrative(with_docs=True)
    html = gp.render_html(m)
    pptx = gp.render_pptx(m)
    pdf = gp.render_pdf(m)
    assert "<" in html and "Asset Allocation Proposal" in html
    assert isinstance(pptx, bytes) and pptx[:2] == b"PK"   # zip/OOXML magic
    assert isinstance(pdf, bytes) and pdf[:5] == b"%PDF-"  # PDF magic


def test_deck_shows_the_computed_headline_numbers():
    html = gp.render_html(_with_narrative(with_docs=False))
    assert "$4,919,914" in html   # net worth
    assert "$5,819,914" in html   # gross assets


def test_commentary_slide_present_only_with_narrative():
    with_narr = gp.render_html(_with_narrative(with_docs=True))
    m = make_model(with_docs=True)               # same inputs, no narrative set
    without = gp.render_html(m)
    assert "Investment Commentary" in with_narr
    assert "Investment Commentary" not in without


# --- the v10 fix, end-to-end: documents change the deliverable -------------- #
def test_documents_change_every_export_format():
    no = _with_narrative(with_docs=False)
    yes = _with_narrative(with_docs=True)
    assert gp.render_html(no) != gp.render_html(yes)
    assert gp.render_pdf(no) != gp.render_pdf(yes)
    assert gp.render_pptx(no) != gp.render_pptx(yes)


def test_with_docs_deck_mentions_the_liquidity_event():
    html = gp.render_html(_with_narrative(with_docs=True))
    assert "liquidity" in html.lower()
    assert "liquidity" not in gp.render_html(_with_narrative(with_docs=False)).lower()


def test_deck_carries_the_not_verified_disclaimer():
    html = gp.render_html(_with_narrative(with_docs=True))
    assert "not independently verified" in html.lower() \
        or "not investment advice" in html.lower()
