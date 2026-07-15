# Meridian Family Office Copilot

A B2B copilot that shows family-office staff how AI can help their work: digest a
client's *tuned* bank statements (holdings with PII removed), check them against a
risk mandate, and generate a rebalancing proposal — with the discipline that **every
number is computed deterministically and carries provenance; nothing is invented.**

**v10** — the copilot no longer sorts the client's tactical instructions into typed items.
It assembles ONE self-contained prompt — the intake parameters, the deterministic FACTS (the
only source of numbers), the parsed holdings + raw statement source, the research / other
documents in full, and the client's tactical instructions **verbatim** — and hands it to the
AI to write the proposal. The engine still computes every figure; the LLM narrates around it.
The prompt is shown on the **Proposal** page — editable, copyable, downloadable — so the
client can read it and **test it with alternative LLMs**. With `DEMO_MODE=0` and an
`ANTHROPIC_API_KEY`, the **Generate with Claude** button runs it against the live Claude API.

The Streamlit app (`app.py`) is driven by the real engines:

| Module | Role |
| --- | --- |
| `statement_parser.py` | parse tuned statements (CSV/JSON adapters, FX, reconciliation) |
| `suitability_check.py` | the 8-rule guardrail engine; mandate resolves breach → disclose/flag/block |
| `portfolio_qa.py` | deterministic Q&A tools (+ optional grounded Claude) |
| `datafeed.py` | provenance-first live prices / fees / durations (optional) |

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501, load a sample custodian in the sidebar, press **Digest ▸**,
then use the left-rail nav (Overview / Holdings / Suitability / Data quality / Proposal /
Ask the book).

## Demo mode (POC)

`DEMO_MODE` is **on by default**. It hides the two features that need API keys or a live
network — the live-price fetch and grounded-Claude phrasing — so the app is a clean,
self-contained proof of concept that needs **no keys and no internet**. Everything the
client clicks through (parsing, suitability, proposal, Q&A) runs on the local engines and
the bundled sample statements.

To enable the live features later, set `DEMO_MODE=0` (env var or Streamlit secret) and add
the relevant keys (see `.streamlit/secrets.toml.example`).

## Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repo. These files **must** be committed (they're read at
   runtime): `app.py`, `statement_parser.py`, `suitability_check.py`, `portfolio_qa.py`,
   `datafeed.py`, `requirements.txt`, `.streamlit/config.toml` (the navy/gold theme),
   `synthetic_statements/`, and `reference_table.json`.
2. On https://share.streamlit.io, create a new app pointing at your repo and `app.py`.
3. Leave **Secrets empty** for the POC — it deploys and runs in demo mode as-is.
4. (Later) To turn on live data, add `DEMO_MODE = "0"` plus `FRED_API_KEY` /
   `ANTHROPIC_API_KEY` in the app's Secrets panel.

The rendering, theme, layout and rail nav look the same on Community Cloud as locally; the
platform adds a small viewer badge that can't be fully removed on the free tier.

## Note

`.gitignore` excludes API-key files and `.streamlit/secrets.toml` so credentials never land
in the repo. The statements here are **synthetic** — no real client data.
