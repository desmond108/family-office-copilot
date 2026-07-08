"""narrative.py — the v3 LLM layer: a grounded CIO commentary for the proposal.

Everything else in the app is deterministic; this is the one place an LLM writes
prose. It is kept honest by construction:

  * The prompt hands Claude a FACTS block (the computed figures from
    proposal_model) plus an ANALYST GUIDANCE block (the free-text sleeve notes and
    "additional considerations"). Claude may quote the figures but is instructed
    never to invent, alter, or add a number that is not in FACTS.
  * The assembled prompt is returned so the app can show it to the user (and let
    them edit it) before anything is sent — full transparency.
  * With no API key / in DEMO_MODE, `deterministic_summary()` produces a grounded
    commentary from the same figures with no model call at all, so the feature
    degrades gracefully instead of failing.

Model: claude-opus-4-8 with adaptive thinking (accuracy matters — the note must
not misquote a figure). The call is lazy-imported so `anthropic` stays optional.
"""
from __future__ import annotations

import json

NARR_MODEL = "claude-opus-4-8"

SYSTEM = (
    "You are the Chief Investment Officer of a family office, writing a short "
    "commentary to accompany a portfolio proposal for the firm's staff and the "
    "client. Write 150-220 words in a measured, professional voice, as flowing "
    "prose in 2-3 short paragraphs — no headings, no bullet lists.\n\n"
    "GROUNDING RULES (non-negotiable):\n"
    "1. You may use ONLY figures that appear in the FACTS JSON. Quote them exactly "
    "as written — never invent, estimate, re-round, or introduce any number that "
    "is not in FACTS.\n"
    "2. Weave in the analyst's notes and considerations where they are relevant; "
    "treat them as intent and context, not as sources of new figures.\n"
    "3. Do not give personalised investment advice or guarantees. Frame the note "
    "as 'for discussion'. If a figure needed to make a point is not in FACTS, say "
    "the data is not yet available rather than guessing."
)


def facts_block(model: dict) -> dict:
    """The subset of the computed proposal model handed to the LLM as ground truth."""
    return {
        "as_of": model["as_of"],
        "provenance": model["prov"],
        "portfolio": model["subtitle"],
        "custodians": model["meta"]["custodians"],
        "entities": model["meta"]["entities"],
        "positions": model["meta"]["positions"],
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


def build_prompt(model: dict) -> str:
    """Assemble the user prompt (FACTS + ANALYST GUIDANCE + TASK) shown to the user."""
    facts = json.dumps(facts_block(model), indent=2)
    guidance = guidance_block(model)
    g = "\n".join(f"- {line}" for line in guidance) if guidance else "- (none supplied)"
    return (
        f"FACTS (JSON — the only figures you may use):\n{facts}\n\n"
        f"ANALYST GUIDANCE (intent and context — not a source of numbers):\n{g}\n\n"
        "TASK: Write the CIO commentary described in your instructions, grounded "
        "strictly in the FACTS above and shaped by the analyst guidance."
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
