# Test suite — Meridian Family Office Copilot

Runs **fully offline** in `DEMO_MODE` (no API key, no network, no billing). The
live-model path (`narrative.generate_claude`, `portfolio_qa.ask_ai`) is deliberately
**not** exercised — every test targets the deterministic engine and the keyless
fallback, which is the product's source of truth.

```bash
python3 -m pytest            # whole suite (~11s, 65 tests)
python3 -m pytest tests/test_suitability.py -v
```

## What each file covers

| File | Layer | Scenarios |
| --- | --- | --- |
| `test_statement_parser.py` | Engine · ingestion | 3 custodian formats (USD CSV, European-decimal EUR/CHF CSV, JSON alts + Lombard loan); FX→USD; reconciliation checksum gating; PII-free continuity key; consolidation totals (`gross − debt = net`) |
| `test_suitability.py` | Engine · policy | Mandate semantics (execution_only→disclose, advisory→flag, discretionary→block on the *same* breach); concentration (single-security vs fund, money-market exemption); liquidity floor; unhedged-FX; hard regulatory blocks (sanctions, complex products) under every mandate; instruction-diff (the "BND vs the client's 5-yr Treasury" defect); enforcement ranking |
| `test_portfolio_qa.py` | Engine · Q&A | Routing (net worth, FX, suitability, concentration, liquidity, data quality); answers stay grounded in computed facts; router never crashes on odd phrasings |
| `test_doc_extract.py` | Deliverable · ingestion | txt/md/html/eml/csv/json read deterministically; unsupported types fail gracefully; truncation flagged; stable result shape |
| `test_narrative.py` | Deliverable · prompt | Portable prompt carries every block (FACTS/intake/holdings/docs/tactical); documents embed verbatim; **the v10 fix** — documents change the deterministic commentary; figures are only ever quoted from the model, never invented; disclaimer present |
| `test_generate_proposal.py` | Deliverable · deck | HTML/PPTX/PDF render with valid magic bytes; headline numbers appear; commentary slide present only with a narrative; **documents change every export format**; the liquidity event surfaces with docs; "not verified" disclaimer present |
| `test_app_scenarios.py` | App · end-to-end | Streamlit `AppTest`: app boots; each sample loads; core views (Overview/Holdings/Suitability/Proposal) render without error; the prompt + commentary appear; tactical instructions reach the prompt; changing the mandate changes the gate; single-custodian book still produces a proposal; no-book views degrade gracefully |

## Design notes

- `conftest.py` provides a session `book` fixture (the reconciled 3-custodian sample)
  and `make_model(with_docs=…, mandate=…, tactical=…)`, a complete deck model matching
  `app.proposal_model`'s output shape so `narrative.py` + `generate_proposal.py` can be
  tested without Streamlit.
- App scenarios inject statements into `session_state` directly (the same object the
  sidebar's **Analyse ▸** writes), because `AppTest` can't populate a `file_uploader`.
- The central invariant under test: **every number is deterministic; documents and
  instructions are advisory context that shape prose, never figures.**
