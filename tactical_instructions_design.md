# Design note — ad-hoc tactical instructions in the UI

**Q (partner):** how do we handle very ad-hoc, varied client asks — *"buy in tranches"*,
*"rate-hike expectations"*, *"low fees, good quality"*? Just another free-text box?

**A:** Keep a free-text box — but as the *input*, not the storage. A single box is the weakest
option for this product. Small fix, and it reuses what we already built.

## The insight: varied ≠ unstructured

Every ad-hoc line in the client's message falls into one of **four types**:

| Client's words | Type |
|---|---|
| "add Nasdaq only after a 15–20% pullback"; "gold below USD 4,000/oz" | **Entry trigger** (a level to watch) |
| "buy the bond fund in tranches"; "an initial 5%, park the rest" | **Execution style** |
| "low fees, good liquidity, good quality" | **Selection criteria** |
| "what's the impact of rate-hike expectations?" | **Open question** |

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

## What's built (prototype, working)

- **Intake page:** a *Tactical instructions* box → **Sort into items** → an editable review table →
  **Confirm**. Confirmed triggers show as a **📡 monitoring watchlist**; everything folds into the
  proposal as guidance (never into the figures).
- Works **with or without** an API key (a keyword fallback runs the demo build).
- Tested on the client's own message: both triggers captured *with their levels*, the tranche
  instruction and rate-hike question split apart, all figures still computed deterministically.

## Limits / next

- The watchlist is **captured, not yet live-monitored** — wiring it to price checks is the natural
  next step (and the highest-value one).
- Selection criteria are captured as guidance, not yet a live product screen.

**Bottom line:** yes to a free-text box — as the capture surface, not the format. Sorting into four
typed items (human-confirmed) turns ad-hoc guidance into things the copilot can act on and monitor,
without ever letting the model invent a number.
