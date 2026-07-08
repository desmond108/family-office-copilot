# v3 — Grounded LLM CIO Commentary

**Status:** shipped · **Module:** `narrative.py` · **Model:** `claude-opus-4-8` (adaptive thinking)

Version 3 adds the **one place in the app where an LLM writes prose** — a short,
CIO-letter-style commentary layered on top of the otherwise fully deterministic proposal
deck. Everything else (tables, weights, trades, charts, the suitability gate) stays
computed by the engines. The narrative is kept honest **by construction**, not by trust.

---

## The discipline: FACTS vs. GUIDANCE

The prompt handed to Claude has two clearly separated blocks:

| Block | Contents | Claude may… |
| --- | --- | --- |
| **FACTS** (JSON) | The computed proposal figures — net worth, gross, liabilities, leverage, allocation-vs-target, rebalance trades, suitability gate + findings, data-quality flags | **Quote them exactly.** Never invent, estimate, re-round, or introduce a number not in FACTS. |
| **ANALYST GUIDANCE** | The per-sleeve notes + the free-text "additional considerations" | Treat as **intent and context** — shape the narrative, but **not** a source of new figures. |

The system prompt enforces this: *"You may use ONLY figures that appear in the FACTS
JSON… never invent, estimate, re-round, or introduce any number that is not in FACTS."*
Output is 150–220 words, 2–3 paragraphs, framed "for discussion," no advice or guarantees.

---

## Human-in-the-loop: the editable prompt

On the **Proposal** page, a *"💬 CIO commentary"* expander surfaces the **fully assembled
prompt in an editable text area** before anything is sent. The analyst can:

- **Edit** the prompt freely (tweak the ask, trim the guidance) before generating.
- **↻ Rebuild** the prompt from the current inputs after changing parameters.
- **✨ Generate** the commentary, then **✕ Clear** it.

This makes the LLM step transparent and reviewable — nothing is sent silently.

---

## Graceful degradation (DEMO_MODE / no key)

The feature never hard-fails on a missing API key:

- **Claude enabled** (`DEMO_MODE=0` **and** an API key resolves) → `generate_claude()`
  calls `claude-opus-4-8`. A refusal, empty response, or any exception falls back
  automatically to the deterministic path.
- **Otherwise** → `deterministic_summary()` produces a genuinely grounded 3-paragraph
  commentary from the **same figures** with **no model call at all**, and incorporates the
  analyst considerations. The UI shows a 🔒 caption explaining Claude is off.

`anthropic` stays a **lazy, optional import**, so the keyless demo build needs no new
required dependency.

---

## Where the narrative goes

Once generated, it is folded into `model["narrative"]` **before** the downloads are built,
so it appears identically in:

- the **inline HTML** deck on the Proposal page,
- the **PPTX** and **PDF** downloads.

`generate_proposal.py` renders it as an **optional commentary slide immediately after the
cover** in all three formats, shifting the remaining page numbers via an `off` offset
(cover → commentary → position → … → data & method: pages 2–7 when present).

---

## Files touched

| File | Change |
| --- | --- |
| `narrative.py` | **new** — `facts_block`, `guidance_block`, `build_prompt`, `deterministic_summary`, `generate_claude` |
| `app.py` | Proposal page: editable-prompt expander, Generate/Rebuild/Clear, gating, fold into `model["narrative"]` |
| `generate_proposal.py` | optional CIO-commentary slide (HTML/PPTX/PDF) with page-number offset |
| `requirements.txt` | note that `anthropic` now also powers the CIO commentary (optional) |

---

## Verification

- All three renderers produce output with and without a narrative; page numbers run 2–7
  with the commentary as slide 2 (cover unnumbered).
- AppTest on the Proposal view: no exception; editable prompt present; **Generate**
  produces a grounded summary quoting `$4,649,914` net worth / `$5,549,914` gross; Clear
  button appears afterwards.
- `py_compile` clean on `app.py`, `narrative.py`, `generate_proposal.py`.
