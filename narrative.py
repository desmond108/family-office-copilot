"""narrative.py — the v4 LLM layer: a self-contained, portable deck-generation prompt.

Everything else in the app is deterministic; this is the one place an LLM writes
prose. It is kept honest by construction:

  * `build_prompt` assembles a SELF-CONTAINED prompt: it inlines the full role +
    grounding rules, the exact 7-section deck specification (matching
    generate_proposal), a FACTS block (every figure from proposal_model) and an
    ANALYST GUIDANCE block (the free-text sleeve notes and "additional
    considerations"). Because nothing is hidden in a separate system message, the
    prompt can be COPIED VERBATIM into any LLM chat to regenerate the same
    proposal deck as a PPTX and a PDF. The LLM may quote the FACTS figures but is
    instructed never to invent, alter, or add a number that is not in FACTS.
  * The assembled prompt is returned so the app can show it to the user, let them
    edit it, and copy it — full transparency.
  * With no API key / in DEMO_MODE, `deterministic_summary()` produces a grounded
    commentary from the same figures with no model call at all, so the in-app
    commentary degrades gracefully instead of failing.

Model: claude-opus-4-8 with adaptive thinking (accuracy matters — the deck must
not misquote a figure). The call is lazy-imported so `anthropic` stays optional.
"""
from __future__ import annotations

import json

NARR_MODEL = "claude-opus-4-8"

# The prompt built by build_prompt() is fully self-contained (all instructions are
# in the user message so it stays portable), so the API system message is kept
# minimal and neutral — it only reinforces the grounding rule.
SYSTEM = (
    "You are a private-banking portfolio analyst assistant. Follow the user's "
    "prompt exactly. Use ONLY the figures given in the prompt's FACTS block — "
    "never invent, estimate, re-round, or alter a number."
)


def facts_block(model: dict) -> dict:
    """The subset of the computed proposal model handed to the LLM as ground truth."""
    return {
        "title": model["title"],
        "as_of": model["as_of"],
        "provenance": model["prov"],
        "portfolio": model["subtitle"],
        "custodians": model["meta"]["custodians"],
        "custodian_list": model["custodian_list"],
        "entities": model["meta"]["entities"],
        "positions": model["meta"]["positions"],
        "gross_assets_total": model["gross_str"],
        "mandate": model["meta"]["mandate"],
        "risk_appetite": model["meta"]["risk"],
        "ability_to_take_risk": model["meta"]["ability"],
        "headline_metrics": {label: value for label, value in model["metrics"]},
        "allocation_vs_target": [
            {"sleeve": r[0], "value_usd": r[1], "pct_of_gross": r[2],
             "target": r[3], "drift": r[4]} for r in model["alloc_rows"]
        ],
        "rebalancing": {
            "trades": [{"sleeve": r[0], "before": r[1], "target": r[2],
                        "trade_usd": r[3], "action": r[4], "note": r[5]}
                       for r in model["reb_rows"]],
            "buys": model["reb_summary"]["buys"],
            "sells": model["reb_summary"]["sells"],
            "net_of_trades": model["reb_summary"]["net"],
            "self_funding": model["reb_summary"]["selffund"],
        },
        "suitability_gate": model["gate"],
        "suitability_findings": [f"[{e}] {d}" for e, d in model["suit_items"]],
        "data_quality_flags": [f"{k}: {d}" for k, d in model["data_quality"]],
    }


def guidance_block(model: dict) -> list[str]:
    """The analyst's free-text notes / overlays / considerations (intent, not facts)."""
    lines = list(model.get("overlays") and
                 [f"Overlay sleeve target: {o}" for o in model["overlays"]] or [])
    lines += list(model.get("analyst_notes") or [])
    return lines


# The deck specification — the 7 sections, in order, matching generate_proposal's
# renderers. Inlined into the prompt so an external LLM reproduces the same deck.
DECK_SPEC = """\
You are a private-banking portfolio analyst. Build a client PORTFOLIO PROPOSAL deck from the \
FACTS below and produce it as BOTH a Microsoft PowerPoint (.pptx) file and a PDF (.pdf) file, \
ready to download.

ABSOLUTE GROUNDING RULE: every number in the deck must be copied verbatim from the FACTS JSON. \
Never invent, estimate, re-round, or add a figure that is not in FACTS. You may write the \
labels and prose; you may not write a figure that is not in FACTS. If a number needed to make a \
point is missing, say the data is not yet available rather than guessing.

HOUSE STYLE: landscape 16:9 slides, one slide per section below. Navy #1e2a56 titles on white, \
gold #b0872a eyebrows/accents, muted slate #5a648a body notes; a full-navy cover slide. Put a \
footer on every content slide: "Portfolio Proposal · Confidential". Measured, professional tone.

SLIDES (produce them in this exact order):
1. COVER (full navy background). Eyebrow "PORTFOLIO PROPOSAL · CONFIDENTIAL". Title = FACTS.title. \
Subtitle = FACTS.portfolio. One lede line: "Generated from {FACTS.custodians} parsed custodian \
statement(s) across {FACTS.entities} entit(y/ies) · {FACTS.positions} positions. Every figure is \
computed from the client's own holdings — nothing is invented." Bottom stamp: "As of {FACTS.as_of}".
2. INVESTMENT COMMENTARY. Eyebrow "Investment Commentary", title "Chief Investment Office — \
Commentary". Write a 150-220 word CIO commentary in 2-3 short paragraphs (no headings, no bullets), \
measured and professional, grounded strictly in FACTS and shaped by the ANALYST GUIDANCE (guidance \
is intent/context, not a source of numbers). End with a small note: this is generated prose that \
quotes but does not alter the figures — for discussion only, not investment advice.
3. CURRENT CONSOLIDATED POSITION. Eyebrow "Position". Show each FACTS.headline_metrics entry as a \
metric card (label above value). Below the cards: "Mandate {FACTS.mandate} · Risk appetite \
{FACTS.risk_appetite} · Ability to take risk {FACTS.ability_to_take_risk}."; then "Consolidated \
across {FACTS.custodian_list joined by commas}."; then the FACTS.provenance line.
4. CURRENT ALLOCATION VS TARGET. Eyebrow "Allocation". A table with columns [Asset class, \
Value (USD), % of gross, Target, Drift] — one row per FACTS.allocation_vs_target entry (sleeve, \
value_usd, pct_of_gross, target, drift) — plus a bold total row \
["Gross assets", FACTS.gross_assets_total, "100.0%", "", ""]. Note underneath: weights are computed \
from parsed statement values against the mandate target; sleeves with no target are flagged on the \
suitability slide, not treated as compliant by omission.
5. REBALANCING PROPOSAL — BEFORE → AFTER. Eyebrow "Proposal". A table with columns [Sleeve, Before, \
Target, Trade (USD), Action, Note] — one row per FACTS.rebalancing.trades entry. Below: "Buys \
{FACTS.rebalancing.buys} · Sells {FACTS.rebalancing.sells} · Net of trades \
{FACTS.rebalancing.net_of_trades}" and state whether the programme is self-funding \
(FACTS.rebalancing.self_funding).
6. SUITABILITY OF THE PROPOSED BOOK. Eyebrow "Suitability". Line "Mandate gate · \
{FACTS.suitability_gate}". Then list every FACTS.suitability_findings item; if the list is empty, \
state the book is within all defined suitability bands.
7. DATA QUALITY, ANALYST NOTES & PROVENANCE. Eyebrow "Data & Method". Left column: list every \
FACTS.data_quality_flags item (or "No data-quality issues detected." if empty). Right column: the \
ANALYST GUIDANCE items, folded into the proposal. Close with the FACTS.provenance line and "For \
discussion only; not investment advice."

If your environment cannot create files, instead output the full slide-by-slide content in the \
exact order above so it can be pasted into slides."""


def build_prompt(model: dict) -> str:
    """Assemble the self-contained, portable deck-generation prompt shown to the
    user. Copied verbatim into any LLM chat it regenerates this proposal as a PPTX
    and a PDF, using only the FACTS figures."""
    facts = json.dumps(facts_block(model), indent=2)
    guidance = guidance_block(model)
    g = "\n".join(f"- {line}" for line in guidance) if guidance else "- (none supplied)"
    return (
        f"{DECK_SPEC}\n\n"
        f"FACTS (JSON — the only figures you may use):\n{facts}\n\n"
        f"ANALYST GUIDANCE (intent and context — NOT a source of numbers):\n{g}"
    )


def deterministic_summary(model: dict) -> str:
    """A grounded commentary assembled with NO model call — used in DEMO_MODE or
    when no API key is available. Quotes the same computed figures verbatim."""
    m = dict(model["metrics"])
    meta = model["meta"]
    rs = model["reb_summary"]
    ent = "entity" if meta["entities"] == 1 else "entities"
    fund = ("nets to approximately zero and is self-funding" if rs["selffund"]
            else "requires external cash or raises net proceeds")
    breaches = len(model["suit_items"])
    gate = model["gate"]
    gate_line = (
        "the book sits within all defined suitability bands"
        if gate == "none" else
        f"the mandate gate is '{gate}', with {breaches} item(s) flagged for review")
    dq = model["data_quality"]
    dq_line = (
        " Data quality is clean." if not dq else
        f" {len(dq)} data-quality item(s) — including "
        f"{dq[0][1]} — should be resolved before the book is treated as final.")
    notes = model.get("analyst_notes") or []
    note_line = (" Analyst considerations incorporated: " + "; ".join(notes) + "."
                 if notes else "")

    p1 = (
        f"This consolidated portfolio carries a net worth of {m.get('Net worth', 'n/a')} "
        f"on gross assets of {m.get('Gross assets', 'n/a')} "
        f"(liabilities {m.get('Liabilities', 'n/a')}, leverage "
        f"{m.get('Leverage (debt/net)', 'n/a')}), parsed from {meta['custodians']} "
        f"custodian statement(s) across {meta['entities']} {ent} as of {model['as_of']}. "
        f"The mandate is {meta['mandate']}, with a {meta['risk']} risk appetite and "
        f"{meta['ability']} ability to take risk; liquid assets stand at "
        f"{m.get('Liquid assets', 'n/a')} of gross.")
    p2 = (
        f"Measured against policy, {gate_line}. The rebalancing proposal directs "
        f"{rs['buys']} of purchases and {rs['sells']} of sales; the programme "
        f"{fund}.{dq_line}")
    p3 = (
        f"We recommend executing the sleeve moves as tabled and resolving any flagged "
        f"items before implementation.{note_line} This commentary is for discussion "
        f"only and is not investment advice.")
    return f"{p1}\n\n{p2}\n\n{p3}"


def generate_claude(user_prompt: str, api_key: str, system: str = SYSTEM):
    """Send the (possibly user-edited) prompt to Claude. Returns (text, source).
    Any failure degrades to the caller's deterministic fallback."""
    import anthropic  # lazy — keeps the dep optional for the keyless demo build
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=NARR_MODEL, max_tokens=1024,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    if msg.stop_reason == "refusal":
        raise RuntimeError("model declined the request")
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    if not text:
        raise RuntimeError("empty response")
    return text, "claude"
