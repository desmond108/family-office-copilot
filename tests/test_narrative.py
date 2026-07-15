"""Deliverable · prompt + narrative — the portable prompt bundles FACTS + intake +
holdings + documents + tactical text; the deterministic summary (keyless fallback)
must REFLECT the documents (the v10 fix) while never sourcing numbers from them."""
from __future__ import annotations

import json
import re

import narrative
from conftest import make_model


# --- the portable prompt carries every input block -------------------------- #
def test_prompt_contains_all_blocks():
    p = narrative.build_prompt(make_model(with_docs=True)).upper()
    for block in ("FACTS", "INTAKE", "HOLDINGS", "STATEMENT", "RESEARCH",
                  "OTHER", "TACTICAL", "GUIDANCE"):
        assert block in p, f"prompt missing the {block} block"


def test_prompt_embeds_document_text_verbatim():
    p = narrative.build_prompt(make_model(with_docs=True))
    assert "liquidity event" in p.lower()       # from the client email
    assert "range-bound us equity" in p.lower() # from the CIO note


def test_prompt_without_docs_omits_that_content():
    p = narrative.build_prompt(make_model(with_docs=False))
    assert "liquidity event" not in p.lower()


def test_facts_block_is_valid_json_and_holds_the_numbers():
    fb = narrative.facts_block(make_model())
    s = json.dumps(fb)  # must be serialisable — it's sent as JSON
    assert "$4,919,914" in s          # net worth rides in FACTS
    assert fb["headline_metrics"]["Net worth"] == "$4,919,914"


# --- the v10 fix: documents shape the deterministic narrative --------------- #
def test_deterministic_summary_reflects_documents():
    with_docs = narrative.deterministic_summary(make_model(with_docs=True))
    no_docs = narrative.deterministic_summary(make_model(with_docs=False))
    assert with_docs != no_docs, "documents must change the commentary"
    assert "liquidity" in with_docs.lower()
    assert "liquidity" not in no_docs.lower()


def test_supplied_context_quotes_tactical_and_docs():
    ctx = narrative.supplied_context(make_model(with_docs=True))
    joined = " ".join(ctx).lower()
    assert ctx, "expected supplied-context excerpts"
    assert "4,000" in joined or "tranche" in joined   # tactical text
    assert "liquidity" in joined or "500k" in joined  # a document


def test_deterministic_summary_quotes_computed_figures_only():
    """The keyless summary must use the model's own numbers verbatim and never
    invent a figure that isn't already somewhere in the computed model."""
    model = make_model(with_docs=True)
    text = narrative.deterministic_summary(model)
    assert "$4,919,914" in text
    # Every dollar figure in the prose must already exist in the model's content.
    haystack = json.dumps(narrative.facts_block(model)) + str(model["data_quality"]) \
        + str(model["analyst_notes"])
    for m in re.findall(r"\$[\d,]*\d", text):   # no trailing comma from prose
        assert m in haystack, f"summary introduced an un-sourced figure {m}"


def test_deterministic_summary_carries_the_disclaimer():
    text = narrative.deterministic_summary(make_model())
    assert "not investment advice" in text.lower()
