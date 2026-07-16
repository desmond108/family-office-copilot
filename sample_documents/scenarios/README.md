# Business scenarios — live tests for v10 (Streamlit Cloud, live API)

Three diverse, ready-to-run scenarios for testing the deployed v10 app with the live AI
model. Each bundle has the inputs to reproduce the scenario end to end:

| # | Scenario | Macro overlay to select | Tactical text | Research doc (§2) | Other doc (§3) |
| --- | --- | --- | --- | --- | --- |
| 1 | **Rate cuts** (monetary policy) | `Rate cuts expected` | `1_rate_cuts/tactical_instruction.txt` | `Meridian_CIO_Rates_Outlook.md` | `Client_Email_Rates.eml` |
| 2 | **Geopolitical shock** (war → defensive/alternatives) | `Geopolitical risk-off` | `2_geopolitical_shock/tactical_instruction.txt` | `Alpine_Global_Geopolitical_Risk_Note.md` | `RM_Internal_Note_Geopolitics.txt` |
| 3 | **US tax hike** (fiscal, non-US person) | `US tax drag (non-US person)` | `3_us_tax_hike/tactical_instruction.txt` | `Meridian_Tax_Policy_Brief.md` | `Client_Email_Tax.eml` |

All files are synthetic — no real client data. They're coherent with the built-in
Kadir / UOB book (10% money-market · 20% gold · 20% bonds · 20% Nasdaq-100 · 30% S&P 500).

## Two layers move — on purpose

- **The macro overlay MOVES THE NUMBERS.** Selecting an overlay applies a deterministic,
  bounded tilt to the *target* allocation, so the rebalancing recommendation shifts in
  the scenario's direction. The tilt is a fixed, documented rule (never model-invented),
  sums to zero, and the suitability bands stay on the strategic policy.
- **The tactical text + documents SHAPE THE WRITE-UP.** They flow to the AI as context so
  the commentary explains the view. They never change a figure.

Every number still comes from the parsed statements and the deterministic engine.

## How to run each test (deployed v10)

1. **Sidebar §1 · Client documents** — load a sample statement (e.g. *UOB Private Bank*),
   press **Analyse ▸**. You now have a baseline proposal.
2. **Intake page** — under **Macro overlay**, select the overlay for the scenario (table
   above). A *Target tilt* line shows the sleeves that moved.
3. **Intake page** — paste the scenario's `tactical_instruction.txt` into **Tactical
   instructions**.
4. **Sidebar §2 / §3** — upload the research doc under *Research documents* and the other
   doc under *Other documents*.
5. **Press Analyse ▸ again** — this commits the documents (v10 reads them only on Analyse,
   never on upload).
6. **Proposal page** — you'll see the **"Macro overlay applied"** banner and the shifted
   rebalancing table. Press **✨ Generate commentary** to have the live AI write the
   narrative around the new numbers and the documents.

**Tip — see the contrast:** run the baseline first with the overlay set to *No macro
overlay* and note the rebalance trades + commentary; then apply the scenario and compare.

## What to look for

- **Rate cuts** → target **fixed income ↑, cash ↓**; the recommendation deploys parked
  cash into bonds; commentary talks *extend duration / build in tranches / reinvestment
  risk*.
- **Geopolitical risk-off** → target **equity ↓, gold + cash ↑**; the recommendation
  trims risk and raises safe havens; commentary talks *defensive tilt, dry powder, defer
  equity adds*.
- **US tax hike** → target **equity ↓, gold ↑** (trim US-situs at the margin); commentary
  talks *withholding / estate drag, Irish-UCITS / accumulating wrappers, no gain-triggering
  churn*.

In all three, the tables/numbers move **only** by the documented overlay tilt; the AI adds
the reasoning, never a figure.

*(File formats: `.txt` / `.md` / `.eml` upload directly. Tactical text goes in the text
box, not the uploader.)*
