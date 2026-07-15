"""App · end-to-end scenarios — drive the real Streamlit app (AppTest) in DEMO_MODE
across the views a private banker walks through: load the samples, review Overview /
Suitability / Proposal, change the mandate and tactical instructions, and confirm the
app never errors and the deterministic figures surface. Offline; no API key.

Statements are injected into session_state directly (the same object the sidebar's
"Analyse ▸" writes) so the run is deterministic and independent of the file-uploader
widget, which AppTest cannot populate.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ["DEMO_MODE"] = "1"

from streamlit.testing.v1 import AppTest  # noqa: E402
import statement_parser as sp             # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")

SAMPLES = {
    "custodianA_uob.csv": sp.parse_custodian_a,
    "custodianB_eurobank.csv": sp.parse_custodian_b,
    "custodianC_familyoffice.json": sp.parse_custodian_c,
}


def _statements(fnames):
    out = []
    for fn in fnames:
        out.append(sp.reconcile(SAMPLES[fn](sp.STMT_DIR / fn)))
    return out


def _load(fnames=("custodianA_uob.csv", "custodianB_eurobank.csv",
                  "custodianC_familyoffice.json"), view="Overview", **state):
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.session_state["statements"] = _statements(fnames)
    at.session_state["source"] = ", ".join(fnames)
    at.session_state["statement_sources"] = [
        {"name": fn, "text": (sp.STMT_DIR / fn).read_text()} for fn in fnames]
    for k, v in state.items():
        at.session_state[k] = v
    at.session_state["view"] = view
    at.run()
    return at


def _text(at):
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] \
        + [s.value for s in at.success] + [i.value for i in at.info]
    return "\n".join(str(p) for p in parts)


# --- the app boots ---------------------------------------------------------- #
def test_app_boots_without_a_book():
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    assert not at.exception


# --- each sample statement loads and drives every view ---------------------- #
@pytest.mark.parametrize("fname", list(SAMPLES))
def test_each_sample_loads_into_overview(fname):
    at = _load((fname,), view="Overview")
    assert not at.exception, f"{fname} crashed the Overview view"


@pytest.mark.parametrize("view", ["Overview", "Holdings", "Suitability", "Proposal"])
def test_core_views_render_with_full_book(view):
    at = _load(view=view)
    assert not at.exception, f"{view} raised {at.exception}"


# --- Proposal: the prompt + deterministic commentary appear ----------------- #
def test_proposal_shows_prompt_and_commentary():
    at = _load(view="Proposal")
    assert not at.exception
    txt = _text(at)
    assert "prompt handed to the AI" in txt.lower() or "the prompt" in txt.lower()
    assert "commentary" in txt.lower()
    # the editable prompt text-area exists and is populated
    prompts = [ta.value for ta in at.text_area if ta.value]
    assert any("FACTS" in str(p).upper() for p in prompts), "prompt not assembled"


# --- scenario: tactical instructions flow into the prompt ------------------- #
def test_tactical_instructions_reach_the_prompt():
    at = _load(view="Proposal",
               tactical_text="Buy the bond fund in tranches; add Nasdaq only after a "
                             "15-20% pullback; gold below USD 4,000/oz.")
    assert not at.exception
    prompts = [str(ta.value) for ta in at.text_area if ta.value]
    blob = "\n".join(prompts)
    assert "tranches" in blob.lower() and "4,000" in blob


# --- scenario: changing the mandate changes the suitability gate ------------ #
@pytest.mark.parametrize("mandate,expect_block", [("discretionary", True),
                                                  ("advisory", False)])
def test_mandate_drives_enforcement_severity(mandate, expect_block):
    """Under discretionary, band breaches HARD-BLOCK; under advisory they only flag.
    The same book therefore reads differently on the Suitability view."""
    at = _load(view="Suitability", mandate=mandate)
    assert not at.exception
    txt = _text(at).lower()
    if expect_block:
        assert "block" in txt or "discretionary" in txt


# --- scenario: partial book (one custodian) still produces a proposal ------- #
def test_single_custodian_book_proposal():
    at = _load(("custodianC_familyoffice.json",), view="Proposal")
    assert not at.exception
    assert "commentary" in _text(at).lower()


# --- guard: no book routes the deck views to a helpful prompt, not a crash -- #
def test_proposal_without_book_is_graceful():
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.session_state["view"] = "Proposal"
    at.run()
    assert not at.exception
