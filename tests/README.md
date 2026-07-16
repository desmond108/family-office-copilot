# Test suite — Meridian Family Office Copilot

Runs **fully offline** in `DEMO_MODE` (no API key, no network, no billing). The
live-model path (`narrative.generate_claude`, `portfolio_qa.ask_ai`) is deliberately
**not** exercised — every test targets the deterministic engine and the keyless
fallback, which is the product's source of truth.

```bash
python3 -m pytest            # whole suite (135 tests)
python3 -m pytest tests/test_suitability.py -v
```

## Report deliverables

`python3 tests/build_report.py` runs the suite and regenerates the styled test
report from the live results — `Meridian_Copilot_Test_Report_v10.docx` / `.pptx`
in the repo root, plus `_v10_document.pdf` / `_v10_slides.pdf` when a LibreOffice
`soffice` binary is available (PDFs are skipped gracefully otherwise). Paths derive
from the script location, so it runs from any working directory.

## What each file covers

| File | Layer | Scenarios |
| --- | --- | --- |
| `test_statement_parser.py` | Engine · ingestion | 3 custodian formats (USD CSV, European-decimal EUR/CHF CSV, JSON alts + Lombard loan); FX→USD; reconciliation checksum gating; PII-free continuity key; consolidation totals (`gross − debt = net`) |
| `test_suitability.py` | Engine · policy | Mandate semantics (execution_only→disclose, advisory→flag, discretionary→block on the *same* breach); concentration (single-security vs fund, money-market exemption); liquidity floor; unhedged-FX; hard regulatory blocks (sanctions, complex products) under every mandate; instruction-diff (the "BND vs the client's 5-yr Treasury" defect); enforcement ranking |
| `test_portfolio_qa.py` | Engine · Q&A | Routing (net worth, FX, suitability, concentration, liquidity, data quality); answers stay grounded in computed facts; router never crashes on odd phrasings |
| `test_doc_extract.py` | Deliverable · ingestion | txt/md/html/eml/csv/json read deterministically; unsupported types fail gracefully; truncation flagged; stable result shape |
| `test_narrative.py` | Deliverable · prompt | Portable prompt carries every block (FACTS/intake/holdings/docs/tactical); documents embed verbatim; **the v10 fix** — documents change the deterministic commentary; figures are only ever quoted from the model, never invented; disclaimer present |
| `test_generate_proposal.py` | Deliverable · deck | HTML/PPTX/PDF render with valid magic bytes; headline numbers appear; commentary slide present only with a narrative; **documents change every export format**; the liquidity event surfaces with docs; "not verified" disclaimer present |
| `test_app_scenarios.py` | App · end-to-end | Streamlit `AppTest`: app boots; each sample loads; core views (Overview/Holdings/Suitability/Proposal) render without error; the prompt + commentary appear; tactical instructions reach the prompt; changing the mandate changes the gate; single-custodian book still produces a proposal; no-book views degrade gracefully; commentary does **not** auto-generate (button-gated) |
| `test_business_scenarios.py` | Business | What happens to the output on a client **macro view** — a rate hike/cut, a war (or its end) prompting alternatives, a tax rise/cut — supplied as either a tactical instruction or a document: (1) it reaches the AI verbatim, (2) it **shapes the commentary**, (3) it **never moves the grounded figures** (FACTS identical with/without it), (4) the interest-rate tool reports bond exposure but refuses to fabricate an unsourced +100bp impact |
| `test_macro_overlay.py` | Business | The **macro overlay** that deliberately **moves the recommendation**: each scenario (rate cuts/hikes, geopolitical risk-off/risk-on, US tax drag) is a fixed, bounded, provenanced tilt of the target allocation — asserts the direction each sleeve moves, that tilts sum to zero (fully invested), nothing goes negative, `none` is a no-op, and a clamped tilt still balances. Plus an end-to-end check that selecting an overlay moves the target in the live proposal |

## Design notes

- `conftest.py` provides a session `book` fixture (the reconciled 3-custodian sample)
  and `make_model(with_docs=…, mandate=…, tactical=…)`, a complete deck model matching
  `app.proposal_model`'s output shape so `narrative.py` + `generate_proposal.py` can be
  tested without Streamlit.
- App scenarios inject statements into `session_state` directly (the same object the
  sidebar's **Analyse ▸** writes), because `AppTest` can't populate a `file_uploader`.
- The central invariant under test: **every number is deterministic; documents and
  instructions are advisory context that shape prose, never figures.**
