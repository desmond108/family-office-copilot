# Design note — ad-hoc tactical instructions in the UI (v10)

**Q (partner):** how do we handle very ad-hoc, varied client asks — *"buy in tranches"*,
*"rate-hike expectations"*, *"low fees, good quality"*, *"gold 20%, S&P 30%…"*? Just another
free-text box?

**A (v10):** Yes — a free-text box, and we pass the client's words **verbatim to the AI model**
together with everything else the copilot knows, in **one self-contained prompt**. The AI analyses
that material and writes the proposal. We no longer sort the instructions into typed items first.

> **This supersedes v6–v8.** Earlier versions sorted the free text into typed items
> (*Sort into items → review → confirm*), tagged each with an enforcement tier (🔒/📡/📝), and let a
> confirmed price trigger gate a rebalance row. v10 removes that pipeline. The earlier design is
> preserved in git history and in `app_v9.py`; the sections below describe the **current** flow.

## The v10 shift: from *classify-then-act* to *pass-through-to-AI*

The old insight still holds — varied ≠ unstructured — but modern AI models read that variety
directly. So instead of a bespoke classifier + review table + enforcement door, v10 hands the raw
inputs to the model and makes the **prompt itself the product surface**: it is shown on the Proposal
page, fully **visible, editable, copyable and downloadable**, so the client can read exactly what the
system asks the model to do and **test it with alternative AI models**.

What the copilot assembles into that single prompt:

| Block | Content | Role |
|---|---|---|
| **Role + grounding rules** | analyst persona; "FACTS is the only source of numbers" | instruction |
| **Intake parameters** | mandate, risk/ability, objective, horizon, limits, exclusions, target allocation | policy |
| **FACTS (JSON)** | allocation, drift, rebalance, suitability — **computed by the engine** | the only numbers |
| **Client holdings + raw statement source** | parsed positions *and* the source text | ground truth |
| **Research / Other documents** | full extracted text | advisory context |
| **Client tactical instructions** | the client's words, **verbatim** | intent / context |

## The guardrail is unchanged: the model never invents a number

Every figure in the deck is still computed **deterministically** by the engine (parser →
suitability → rebalancer) and handed to the model as the **FACTS** block. The model may *quote* those
figures but is instructed never to invent, alter or re-round one. The tactical instructions,
parameters and documents are **context that shapes the prose**, never a source of figures.

New, explicit disclosure in v10: because the model now reads the client's documents and instructions
directly, the deck's commentary note states that **qualitative** statements draw on that supplied
context and are **not independently verified** — for discussion only, not investment advice. The
*numbers* stay deterministic; only the *narrative* reflects the documents.

## Where transparency now lives: the prompt

Old transparency = a review table where the analyst confirmed each sorted item. v10 transparency =
the **prompt on the Proposal page**. The analyst (and the client) can:

- **Read** the entire instruction the system sends — nothing is hidden in a system message.
- **Edit** it before generating (e.g. tighten the brief, drop a document).
- **Copy / download** it and paste it into **any** AI model (the app labels the model generically as
  the *AI Model* — the system is model-agnostic) to reproduce the proposal and compare outputs.
- **Generate** in-app against the live AI model (when `DEMO_MODE=0` and an API key is set), or fall
  back to a deterministic grounded summary with no model call.

## The flow, end to end

> **Capture** (paste tactical text + upload documents, set policy) → **Compute** (engine parses the
> book and computes the deterministic FACTS) → **Assemble** (copilot builds the one self-contained
> prompt) → **Generate** (AI model writes the narrative in-app, or the analyst copies the prompt into
> any AI model) → **Deliver** (proposal deck as PPTX / PDF, with the deterministic tables intact).

Three actors: **Client** (gives instructions + documents), **Analyst** (pastes, sets policy, reviews
the prompt, generates/downloads), **Copilot** (computes FACTS, assembles the prompt, runs the AI
model). See `tactical_flow_chart_v2_note.html` for the drawn flow.

## What's built (v10 — live on Streamlit)

- **Intake page:** a *Tactical instructions* free-text box. No sorting, no review table, no
  enforcement tiers — the text flows straight into the prompt.
- **Proposal page:** the full self-contained **prompt** (editable, copyable, downloadable) + a
  **Generate with AI Model** button; the model's narrative folds into the deck as a commentary slide.
- **Deterministic tables everywhere:** allocation, drift, rebalance and suitability are computed by
  the engine and unchanged by the model.
- **Model-agnostic UI:** every user-facing label reads *AI Model*; the prompt works in any LLM.
- Works **with or without** an API key (keyless demo degrades the *Generate* button to a
  deterministic grounded summary; the copy-and-paste prompt still works in any external AI model).

## Trade-offs vs. the v6–v8 pipeline

- **Lost:** the monitoring watchlist, the per-item review/confirm gate, and the one enforced price
  trigger that could gate a trade. If a *binding* conditional rule is needed again, it returns as a
  deterministic check in the engine — never as model output.
- **Gained:** a single, legible, portable prompt the client can inspect and test across models;
  far less UI friction; the model handles fused/ambiguous asks (*"buy in tranches — but what about
  rate hikes?"*) without forcing them into slots.

**Bottom line:** the free-text box stays as the capture surface. v10 stops pre-digesting the client's
words and instead shows — in one transparent, model-agnostic prompt — exactly what the AI is asked to
do, while every number remains computed deterministically by the engine.
