# Reuse Manifest v0 — Building the Private Banker from the other two repos

Maps concrete modules in **Portfolio_Mgr_260627** (PM) and **Hedge_Fund_260701** (HF)
onto the four-layer private-banking architecture and the `data_schema_v0.md` objects.

> **Reuse reality-check (v1, after second-reviewer critique).** An earlier draft said the
> two repos were "the missing two-thirds, already written." That was overstated. Evidence:
> the flagship transfer, `suitability_check.py`, shares **zero lines** with HF's
> `pre_trade.py` — it took ~300 new lines because the original is welded to SQLite, a fixed
> 20-ticker universe, pandas, and long/short semantics. Honest estimate: **~15-25% of the
> needed code transfers, mostly at PATTERN level** (conventions + one liftable alert engine).
> The **BUILD** items — not the lifts — are the actual product. Read "ADOPT" below as
> "adopt the design and the ~80-line algorithm, against your own data layer," not "import it."

Legend: **ADOPT** = use largely as-is · **REPURPOSE** = same machinery, change semantics ·
**PATTERN** = copy the design, rewrite the body · **BUILD** = no donor, write new.

> Note: HF's `CLAUDE.md` says "scaffolding only" but every layer package
> (`factors/`, `portfolio/`, `risk/`, `reporting/`, …) is in fact implemented. Verify
> depth per file before lifting, but the modules exist.

---

## Layer 1 — Data Ingestion → produces `tuned_statement` + live market data

| Need (schema) | Donor | Action | Notes |
|---|---|---|---|
| Market-data spine | HF `data/providers.py` | **ADOPT** | Routes Polygon→prices, FMP→fundamentals, FRED→macro, yfinance/SEC fallback. Better than PM's yfinance-only. |
| Price/quote fetch + normalise | PM `marketdata.py` | **PATTERN** | Keep the *injectable fetcher + normalised plain-Python quote objects* pattern even if you swap the source to `providers.py`. |
| Holdings loader | PM `positions.py` | **PATTERN** | Loads/validates a book into typed objects — closest thing to a `tuned_statement` parser. Extend for multi-entity, cash balances, FX. |
| SQLite store | PM `storage.py` + HF `data/db.py` | **ADOPT** | One store, `INSERT OR REPLACE` keyed on `asof` — idempotent re-runs. Your single source of truth. |
| Statement PII-tuning + parse | — | **BUILD** | Neither repo strips PII or parses a bank statement; both start from a clean file. This is net-new. |
| FX rates + multi-currency valuation | — | **BUILD** | Both repos are effectively USD-only. `base_currency` conversion is new. |
| Alternatives / illiquid manual marks | — | **BUILD** | Family-office assets with stale-valuation flags — no donor. |

---

## Layer 2 — Deterministic Financial Layer → produces `portfolio_analysis`

This is the layer the Fable deck was missing. Almost entirely donor-covered.

| Need (schema field) | Donor | Action | Notes |
|---|---|---|---|
| `position.market_value/unrealized_pnl` | PM `valuation.py` | **ADOPT** | Per-position mark/value/P&L/progress. |
| `current_allocation`, concentration | PM `analytics.py` | **ADOPT** | Allocation by ticker/sector + concentration flags → directly emits `current_allocation` and feeds `suitability_flags`. |
| `risk_metrics.volatility` | HF `risk/factor_risk_model.py` | **ADOPT** | Rolling covariance model → portfolio vol. |
| `risk_metrics.portfolio_beta` | HF `portfolio/beta.py`, `factor_exposure.py` | **ADOPT** | Book beta + factor exposure. |
| diversification / pairwise corr | HF `risk/correlation_monitor.py` | **ADOPT** | Correlation clustering across holdings. |
| `risk_metrics.bond_dv01_pct` | — (use `effective_duration`) | **BUILD** | Small deterministic calc (+100bp → −duration×NAV). Answers Kadir's Q4 without the LLM guessing. Model it on PM `macro.py`'s pure-scorer style. |
| Greeks (if structured products held) | PM `greeks.py` | **ADOPT (optional)** | Stdlib Black-Scholes; only if the book holds options/structured notes. |

---

## The Bridge — Suitability Engine (`risk_profile` × `portfolio_analysis` → `suitability_flags`)

The single most valuable transfer. HF already has a veto engine; you flip its purpose.

| Need | Donor | Action | Notes |
|---|---|---|---|
| `suitability_flags` from bands/limits | HF `risk/pre_trade.py` | **REPURPOSE** | HF checks max-position / gross / net / beta / asset-class-net and **vetoes trades**. Repurpose to evaluate the client's `allocation_bands` + `concentration_limits` and **emit flags**. Then let `mandate` decide flag-vs-block: `execution_only`→surface only, `discretionary`→hard block. |
| "propose a compliant reallocation" | HF `portfolio/mvo_optimizer.py`, `optimizer.py`, `rebalance.py` | **REPURPOSE** | Advisory mode: optimise *toward the client's benchmark within bands* — constrain it, don't let its alpha-seeking objective drive. |
| scenario / stress for the proposal | HF `risk/stress_test.py`, `tail_risk.py` | **REPURPOSE** | "+100bp rates / −20% equity → client's book" = exactly the macro slide + Kadir Q4, computed not narrated. |
| circuit breakers / kill-switch | HF `risk/circuit_breakers.py`, `halt.py` | **DEFER** | Only meaningful for the discretionary (execution) tier. |

---

## Layer 3 — Agentic AI / Reasoning → narrate + real market context

The LLM stays boxed: it narrates verified objects and pulls a real macro reading. Never math.

| Need | Donor | Action | Notes |
|---|---|---|---|
| Narration engine (deck prose) | PM `news.py` | **PATTERN** | The template: Claude behind an *injectable* interface, structured Pydantic output, per-`asof` SQLite cache, and a system prompt that **summarises/flags but never advises**. Rewrite the prompt to narrate `portfolio_analysis` + `suitability_flags` into the proposal. |
| Real macro slide inputs | PM `macro.py` | **ADOPT** | Deterministic 0-100 gate (VIX, breadth, credit). Feeds "Macro Environment" with real numbers — directly fixes the invented `20.1x P/E / 4.7% 10yr` on the Fable deck. |
| Claude cost control | HF `analysis/api_client.py`, `cache.py`, `cost_tracker.py` | **ADOPT** | Prompt caching + `cost_ceiling_per_run_usd`. Deck generation at scale needs this. |
| deterministic + LLM fusion pattern | HF `analysis/combined_score.py` | **PATTERN** | The 60/40 quant/qual blend — conceptual template for "engine facts + LLM narrative," reweighted for advice. |

---

## Layer 4 — Client Interface / Output

| Need | Donor | Action | Notes |
|---|---|---|---|
| Proposal deck (target format) | Fable output (this repo) | reference | The `Portfolio_Proposal_USD3M` deck is the output spec. |
| **Trigger monitoring** (deck slide 11) | PM `alerts.py`, `diff.py` | **ADOPT** ★ | The highest-value, lowest-friction harvest — and the one the first draft missed. Kadir's phased-entry triggers ("gold < $4,000", "NDX −15% from high", "add on pullback") ARE Portfolio_Mgr's core competency: user-defined targets, progress-to-target %, threshold alerts, diff vs prior snapshot. This is the **retention feature** — the deck is one-shot; "your gold trigger fired" is why the client opens the app in October. Feeds the same `SuitabilityFlag`/enforcement channel. |
| Client / RM dashboard | PM `dashboard.py`, `borg.py` (+`borg.html`) | **PATTERN** | Streamlit terminal view over the latest `asof`; reads the db, computes nothing live. |
| **Family-office consolidated reporting** | HF `reporting/` — `tear_sheet.py`, `lp_letter.py`, `commentary.py`, `pnl_attribution.py`, `position_attribution.py`, `macro_performance.py` | **REPURPOSE** | The killer FO feature. LP letter → family quarterly letter; tear sheet → consolidated performance; attribution → "why the book moved." Maps straight onto the multi-entity rollup. |
| persona / theming | HF `dashboard/winthorpe.py`, `theme.py` | **PATTERN** | Client-facing persona + theme scaffolding. |

---

## Execution — Tier 3 (discretionary) only

| Need | Donor | Action | Notes |
|---|---|---|---|
| order routing (paper) | HF `execution/broker.py`, `order_manager.py`, `executor.py`, `costs.py` | **DEFER** | Advisory private banking stops at "proposal"; execution stays with the licensed RM. Adopt only if you build the discretionary tier — keep HF's hardcoded-paper + typed-confirmation guard. |

---

## Cross-cutting spine (adopt across all layers)

- **SQLite single source of truth** — PM `storage.py` / HF `data/db.py`.
- **Config as truth** — PM `config.py` (dataclass) / HF `config.yaml`. Thread it, don't hardcode.
- **Injectable LLM + fetcher** so tests run offline and never bill — both repos already enforce this. Preserve it.

---

## Net gap list (what has NO donor — this is your real build backlog)

1. **Statement PII-tuning + parse** → `tuned_statement` (Layer 1).
2. **Risk-profile capture** (questionnaire → `risk_profile` object).
3. **FX / multi-currency valuation** and `base_currency` consolidation.
4. **Multi-entity rollup** (family office) — `reporting/` gives report *shapes*, not the entity-graph aggregation.
5. **Suitability semantics** — flag-vs-block driven by `mandate`, layered on repurposed `pre_trade.py`.
6. **Bond DV01/duration** deterministic calc.

6. **Bond DV01/duration** deterministic calc.
7. **Instruction-vs-proposal diff** — flag where a recommendation deviates from the
   client's explicit instrument spec (the BND-vs-"5yr Treasury" defect). Built:
   `suitability_check.instruction_diff()`.
8. **Securities reference-data feed** (fund fees, SEC yields, durations, AUM) — every
   *product fact* on the deck (not just market prices) is otherwise LLM-recalled. This is a
   licensing/redistribution-cost problem, not a coding one, and it is unpriced.
9. **Statement ingestion** is a company-sized problem (cf. Flanks/Canoe/Masttro), not the
   one BUILD row it looks like — per-custodian formats, house codes vs ISINs, and a
   contradiction in the "client hand-redacts their own PDF each month" flow (breaks
   `account_ref` continuity → breaks performance).
10. **Transactions + reconciliation** — the schema is positions-only, so no performance /
    realized P&L / income verification, and no free checksum (parsed positions must sum to
    the statement's stated total).

Correcting the earlier framing: the Fable deck is the polished ~20%, but items 1–10 are NOT
"a lift or a repurpose" — most are net-new, and 8–10 are the load-bearing, unscoped work.
The repos give you conventions, one drop-in alert engine, and good templates — not the core.
