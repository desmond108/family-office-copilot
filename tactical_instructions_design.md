# Design note — ad-hoc tactical instructions in the UI

**Q (partner):** how do we handle very ad-hoc, varied client asks — *"buy in tranches"*,
*"rate-hike expectations"*, *"low fees, good quality"*, *"gold 20%, S&P 30%…"*? Just another
free-text box?

**A:** Keep a free-text box — but as the *input*, not the storage. A single box is the weakest
option for this product. Small fix, and it reuses what we already built.

## The insight: varied ≠ unstructured

Every ad-hoc line in the client's message falls into one of a few **recognisable types**:

| Client's words | Becomes |
|---|---|
| "USD money market fund: 10%", "Gold ETF: 20%", "S&P 500 ETF: 30%" | **Target allocation** → *proposed* to the sleeves |
| "add Nasdaq only after a 15–20% pullback"; "gold below USD 4,000/oz" | **Entry trigger** (a level to watch) |
| "buy the bond fund in tranches"; "an initial 5%, park the rest" | **Execution style** |
| "low fees, good liquidity, good quality" | **Selection criteria** |
| "what's the impact of rate-hike expectations?" | **Open question** |
| anything ambiguous, contradictory or unintelligible | **Needs clarification** → held out until resolved |

## Why not one free-text box

Our core rule is: **the system never invents a number.** A free-text box works against it —
"gold below USD 4,000/oz" typed as a note is just prose the model paraphrases. The *same sentence*
as a structured **trigger** is something we can **monitor and alert on** — that's a product feature,
and the retention hook (it plugs into our monitoring repo's `alerts.py`).

A box also hides fused asks: *"buy in tranches — but what about rate hikes?"* is an instruction
**and** a question. Typing them into slots forces them apart.

## The pattern (reuses our v5 statement flow)

> **Free text → the model sorts it into typed items → the human reviews & confirms → structure
> drives the engine.** Anything that doesn't classify stays as free-text guidance.

Same *extract → review → confirm* gate as our PDF/statement ingestion. It keeps the discipline:
the model **only sorts and copies the client's own words** (never invents a level), and a human
**confirms every item** before it counts.

In the review table the analyst is in full control of each row:

- **Keep** (a checkbox) — untick to ignore an item without deleting it; only kept rows are confirmed.
- **Note** — record what to confirm or raise with the client; it travels with the item.
- **Needs clarification** — items the model couldn't act on are shown in a ⚠️ callout and **held out
  of the proposal** until the analyst re-types or removes them. Unclear input never reaches the deck.

## Target allocations: propose, don't auto-fill

When the instructions state target weights, the copilot aggregates them per sleeve
(Nasdaq 20% + S&P 30% → **equity 50%**) and shows a **📥 Proposed allocation** panel. The analyst then:

- **Apply** — fills the allocation sleeves (still adjustable afterward), or
- **Ignore** — keeps their own numbers (dismisses the nudge; a *new*, different set of client weights
  re-surfaces it).

Nothing is ever written silently — the client's stated weights drive the analysis only on an explicit
click. Limits (band tolerance, liquidity, FX, position caps) stay fully manual.

## Enforcement tiers (v8): what actually binds a number

There are endlessly many *conditions* a client can state, but their **shape** clusters into three
handling tiers — so we classify the shape and are honest about what we can enforce today, rather
than writing a rule per condition:

| Tier | Meaning | Example | Data it needs |
|---|---|---|---|
| 🔒 **Enforced** | Binds a computed number — gates a trade | a target weight (via Apply), or *"gold below $4,000"* | a live price for the instrument |
| 📡 **Monitored** | Watched & flagged, can't gate the math yet | *"after a 15–20% pullback"* | a defined reference (trailing high) |
| 📝 **Advisory** | Shapes the write-up only, never a figure | *"buy in tranches"*, *"low fees"*, *"rate hikes?"* | — (a preference or a viewpoint) |

Each confirmed item carries its tier as a **🔒 / 📡 / 📝 badge** in the review table and the watchlist.
The **enforcement door** is narrow on purpose: a confirmed 🔒 *absolute price trigger* on a priceable
instrument is checked against the live [datafeed](datafeed.py) price when you press **Analyse**, and
**annotates the matching rebalance row** — a buy above a *buy-below* level becomes a **HOLD**. The
figure is sourced with provenance and degrades to *"verify manually"* if the feed can't source it, so
the **never-invent-a-number guardrail still holds**: a client condition can *gate or flag* a trade, but
never *fabricate* one. Everything else stays 📡/📝 and never touches a figure.

The honest read: through the door **today, one** of a typical client's conditions (the gold trigger)
actually binds; the value of the tier layer is **transparency** — the deck stops silently implying the
advisory items are enforced. We sell *what's binding*, not a promise to enforce everything.

## What's built (shipped — live on Streamlit)

- **Intake page:** a *Tactical instructions* box → **Sort into items** → an editable review table
  (**Keep / Note / type / level**, with ⚠️ items held out) → **Confirm**. Confirmed triggers show as a
  **📡 monitoring watchlist**; every item folds into the proposal as guidance (never into the figures).
- **Propose → Apply / Ignore** allocation targets when the client stated weights.
- **Enforcement tiers (v8):** every confirmed item is tagged 🔒 / 📡 / 📝; confirmed 🔒 absolute price
  triggers are checked against the live price at **Analyse** and gate the matching rebalance row (buy → hold),
  with provenance — surfaced in the Proposal view, the rebalance table, and the deck notes.
- Works **with or without** an API key (a keyword fallback runs the keyless demo build).
- Verified on the client's own message: allocations mapped per sleeve (=100%), both triggers captured
  *with their levels*, the tranche/rate-hike ask split apart — all figures still computed deterministically.

## Limits / next

- **Monitored → enforced:** relative triggers (a *15–20% pullback*) become enforceable once we define
  their reference point (trailing 52-wk high) — the next increment of the door.
- Selection criteria (*low fees, good liquidity*) stay 📝 advisory until an instrument fee/liquidity
  dataset is wired — the data dependency, not the logic, is the blocker.

**Bottom line:** yes to a free-text box — as the capture surface, not the format. Sorting into typed,
human-confirmed items turns ad-hoc guidance into things the copilot can act on and monitor — proposing
allocations, watching triggers, flagging what's unclear — without ever letting the model invent a number.
