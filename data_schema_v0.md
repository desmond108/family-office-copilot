# Data Schema v0 — Tuned Statement & Risk Profile

Two inputs feed the **deterministic layer** (portfolio math + suitability), which then
feeds the LLM only *verified* numbers to narrate. Nothing here should require the LLM to
invent a figure.

## Design principles

1. **Point-in-time everything.** Valuations and FX rates are only meaningful with an
   `as_of` date. Store the FX rates you used so results are reproducible.
2. **Keep the numbers, drop the identity.** "Tuning" strips names/addresses/account
   numbers — but instrument IDs (ISIN/ticker), quantities, cost basis, and custodian are
   *not* confidential and are required for the math. If tuning removes these, the
   consolidation feature dies.
3. **The risk profile must be machine-actionable.** It's not prose — it encodes
   allocation bands and hard constraints so the engine can flag suitability breaches
   without an LLM judgment call.
4. **Multi-entity from day one.** A private client is the degenerate case (one entity,
   one account) of the family-office model. Same schema, fewer rows.

---

## 1. Tuned Statement

```yaml
tuned_statement:
  schema_version: "0.1"
  as_of_date: 2026-07-01          # all valuations point to this date
  base_currency: USD              # reporting/consolidation currency
  fx_rates:                       # rates used to convert to base_currency, as_of the date
    - { pair: EUR/USD, rate: 1.08 }
    - { pair: SGD/USD, rate: 0.74 }

  entities:                       # ≥1. Private client = single entity.
    - entity_ref: "ENT-A"         # anonymized label (was "The Smith Family Trust")
      entity_type: individual     # individual | joint | trust | holdco | foundation | spv
      tax_jurisdiction: SG        # drives withholding / estate-tax notes

      accounts:
        - account_ref: "ACC-1"    # anonymized (was UOB #1234567)
          custodian: UOB          # NOT confidential — keep it
          account_type: custody   # cash | custody | margin | discretionary | trust
          account_currency: USD

          holdings:
            - instrument:
                id: "US78462F1030"   # ISIN or ticker
                id_type: ISIN        # ISIN | ticker | cusip | internal
                name: "SPDR S&P 500 ETF"
                instrument_type: equity_etf
                # ^ equity_etf | bond_etf | bond_fund | money_market | gold_etf
                #   | single_stock | govt_bond | corp_bond | cash | alternative | real_estate
                asset_class: equity     # equity | fixed_income | commodity | cash | alternatives | real_estate
                sub_class: us_large_cap
                region: US
                sector: broad           # for single names; broad/mixed for funds
                currency: USD
                # classification metrics the engine needs:
                expense_ratio: 0.000945
                effective_duration: null      # years — required for bonds
                yield_30d: 0.012
              position:
                quantity: 500
                price: 660.00               # per unit, in instrument currency, as_of
                market_value: 330000        # instrument currency
                market_value_base: 330000   # converted to base_currency
                cost_basis: 300000          # total, instrument currency
                cost_basis_base: 300000
                unrealized_pnl_base: 30000  # derived, but store for audit
                acquisition_date: 2025-11-15
                income_ytd_base: 1800       # dividends/coupons received YTD

          cash_balances:                    # uninvested cash, per currency
            - { currency: USD, amount: 2500000 }

      liabilities:                          # optional — leverage, Lombard loans, mortgages
        - { liability_ref: "LN-1", type: lombard_loan, currency: USD, balance: 0, rate: null }
```

**Notes**
- `market_value_base` + `asset_class` + `sub_class`/`region` are the minimum to compute
  current allocation, drift, and concentration.
- `effective_duration` and `yield_30d` on bonds are what let the engine answer Kadir's
  rate-hike question deterministically ("+100bp ≈ −6% NAV") instead of the LLM guessing.
- `cash_balances` matter: Kadir is 83% cash in the proposal — that only shows up if cash
  is a first-class holding, not an afterthought.

---

## 2. Risk Profile

```yaml
risk_profile:
  schema_version: "0.1"
  as_of_date: 2026-07-01
  entity_ref: "ENT-A"             # ties to a statement entity; family office may have several
  review_due: 2027-07-01

  mandate: advisory               # execution_only | advisory | discretionary
  # ^ THE key field. Execution_only = do what the client says. Advisory = may challenge.
  #   Discretionary = the app/RM decides within bands. Determines whether suitability
  #   breaches are hard blocks or just flags.

  objective: growth               # preservation | income | balanced | growth | aggressive_growth
  time_horizon_years: 10
  base_currency: USD

  risk_tolerance: moderate        # subjective (questionnaire): conservative..aggressive
  risk_capacity: high             # objective ability to bear loss (wealth vs. needs)
  max_drawdown_tolerance: 0.30    # client-stated pain threshold

  liquidity_need:
    horizon_months: 6
    min_liquid_pct: 0.10          # must stay investable/liquid — drives the cash floor

  # --- Allocation guardrails: what makes suitability checkable ---
  target_allocation:              # strategic benchmark (Kadir's stated mix)
    equity: 0.50
    fixed_income: 0.20
    commodity: 0.20
    cash: 0.10
  allocation_bands:               # min/max per asset class; breach => flag
    equity:       { min: 0.30, max: 0.65 }
    fixed_income: { min: 0.10, max: 0.40 }
    commodity:    { min: 0.00, max: 0.25 }
    cash:         { min: 0.05, max: 0.90 }   # wide max: client wants to sit in cash for now

  concentration_limits:
    max_single_issuer_pct: 0.10
    max_single_position_pct: 0.35   # any one fund
    max_sector_pct: 0.40

  constraints:
    excluded_asset_classes: []      # e.g. [alternatives]
    excluded_sectors: []            # ESG / mandate exclusions, e.g. [tobacco, defense]
    excluded_instruments: []
    currency_constraints:
      base: USD
      max_unhedged_fx_pct: 0.30     # FX risk tolerance

  suitability:                      # regulatory (MAS/MiFID-style)
    knowledge_level: experienced    # inexperienced | informed | experienced | professional
    complex_products_ok: true       # can hold leveraged/structured/derivatives
    accredited_investor: true

  tax:
    residency: SG
    us_person: false                # drives US withholding / estate-tax warnings
    notes: "US-listed ETFs: 30% div withholding, US estate-tax exposure > $60k"
```

**Notes**
- `mandate` is the field most people forget and it changes product behavior entirely.
  Kadir reads as `execution_only`/`advisory` — he's giving instructions. The app should
  *surface* that he's parking 83% in cash against a 50% equity target, but not block him.
- `allocation_bands` + `concentration_limits` + `constraints` are the entire suitability
  engine input. Everything else is context for the narration.
- `tax.us_person` + `currency_constraints` are what let the proposal's FX/withholding
  disclaimer be generated from data rather than boilerplate.

---

## 3. What the deterministic layer computes (the bridge)

Neither input is shown to the client raw. The engine joins them and emits a verified
**analysis object** — this is the only thing the LLM is allowed to narrate:

```yaml
portfolio_analysis:
  as_of_date: 2026-07-01
  total_value_base: 3000000
  current_allocation:            # from statement, by asset_class
    equity: 0.00
    fixed_income: 0.00
    commodity: 0.00
    cash: 1.00
  drift_vs_target:               # current − target
    equity: -0.50
    cash: +0.90
  fx_exposure:
    unhedged_pct: 0.00
  risk_metrics:                  # computed via QuantLib/PyPortfolioOpt, NOT the LLM
    portfolio_beta: null         # null until positions exist
    volatility_annualized: null
    bond_dv01_pct: null          # +100bp NAV impact
  suitability_flags:
    - { rule: equity_band, status: breach, detail: "0% equity vs. min 30% band" }
    - { rule: cash_band, status: ok }
    - { rule: single_position, status: ok }
  income:
    projected_annual_yield: 0.0355   # weighted from holdings' yield_30d
```

The LLM's job is now narrow and safe: turn `suitability_flags` and `drift_vs_target` into
Kadir's prose ("you're currently 100% cash against a 50% equity target…"), and pull live
market data (gold spot, 10-yr yield) from a **feed**, never from its own memory.

---

## 4. Family-office deltas

Same schema, three things switch on:
- **Multiple `entities`** under one profile set → consolidation is just a `group by`
  across entities with FX conversion to a single `base_currency`.
- **`instrument_type: alternative | real_estate`** with manual valuations and
  `as_of` staleness flags (illiquids aren't priced daily).
- **Per-entity `risk_profile`** (a trust and an individual have different mandates/tax),
  plus an optional group-level Investment Policy Statement that sets bands at the
  household level.
```
