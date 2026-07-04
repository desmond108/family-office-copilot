"""build_review.py — render the PARSED consolidated book as a provenance deck.

Where build_deck.py renders a forward proposal from Kadir's stated benchmark, this
renders a portfolio REVIEW of what the client actually holds, parsed from three
tuned custodian statements. Every value traces to its source:
  - holding values  -> the custodian statement (custodian + as_of); stale marks flag
  - FX rates        -> the dated FX table (labelled static-demo)
  - current price / expense ratio -> live yfinance enrichment where the id resolves
  - reconciliation / leverage / weights -> derived, formula shown
Nothing is invented; the generator renders SOURCE REQUIRED before it guesses.

Run (needs network for enrichment; sandbox-off):  python3 build_review.py -> kadir_review.html
"""
from __future__ import annotations

from datetime import date

from datafeed import Feed, Figure, required
from deck_render import STYLE, chip, datum, fmt, kv, slide
from statement_parser import (FX, FX_AS_OF, FX_SOURCE, STMT_DIR, TODAY,
                              continuity_key, parse_custodian_a, parse_custodian_b,
                              parse_custodian_c, reconcile, to_holdings)
from suitability_check import (Bands, RiskProfile, suitability_check, worst_enforcement)

feed = Feed()
# Resolve the few identifiers yfinance knows, for live enrichment.
ISIN_TO_TICKER = {"US78462F1030": "SPY", "US46090E1038": "QQQ", "SGOV": "SGOV"}


def stmt_fig(value, custodian, as_of, note="custodian valuation") -> Figure:
    # Statement marks are point-in-time custodian valuations; treat as fundamental
    # so an old illiquid mark (e.g. a Dec-2025 property NAV) flags as stale.
    return Figure(round(value, 2), "USD", f"{custodian} statement", as_of,
                  kind="fundamental", note=note)


def derived(value, unit, how, as_of=None) -> Figure:
    return Figure(value, unit, "derived", as_of, kind="derived", note=how)


def fx_fig(ccy) -> Figure:
    if ccy == "USD":
        return Figure(1.0, "", "base currency", None, kind="static")
    return Figure(FX[ccy], "", FX_SOURCE, FX_AS_OF, kind="macro", note=f"{ccy}/USD")


# --------------------------------------------------------------------------- #
# Parse + consolidate
# --------------------------------------------------------------------------- #

statements = [
    reconcile(parse_custodian_a(STMT_DIR / "custodianA_uob.csv")),
    reconcile(parse_custodian_b(STMT_DIR / "custodianB_eurobank.csv")),
    reconcile(parse_custodian_c(STMT_DIR / "custodianC_familyoffice.json")),
]
positions = [p for st in statements for p in st.positions]
gross = sum(p.mv_base for p in positions)
debt = sum(abs(lb["balance"]) for st in statements for lb in st.liabilities)
net = gross - debt
AS_OF = statements[0].as_of

# Live enrichment (price + fee) where an id resolves.
enrich = {}
for p in positions:
    tkr = ISIN_TO_TICKER.get(p.identifier)
    if tkr:
        enrich[id(p)] = {"price": feed.last_close(tkr), "fee": feed.expense_ratio(tkr)}

# Allocation by asset class
alloc: dict[str, float] = {}
for p in positions:
    alloc[p.asset_class] = alloc.get(p.asset_class, 0.0) + p.mv_base

# Suitability on the real book
profile = RiskProfile(
    mandate="advisory",
    allocation_bands={"equity": Bands(0.30, 0.65), "fixed_income": Bands(0.10, 0.40),
                      "commodity": Bands(0.00, 0.25), "cash": Bands(0.05, 0.90)},
    min_liquid_pct=0.10)
suit = suitability_check(profile, to_holdings(statements), as_of=TODAY)

# --------------------------------------------------------------------------- #
# Slides
# --------------------------------------------------------------------------- #

s1 = (f'<section class="slide cover"><div class="eyebrow">Portfolio Review · Confidential</div>'
      f'<h1>Consolidated Portfolio Review</h1>'
      f'<p class="sub">{fmt(Figure(net,"USD","",None))} net worth · '
      f'{len(statements)} custodians · 2 entities</p>'
      f'<p class="lede">Parsed from three tuned custodian statements. Every holding value '
      f'traces to its source statement; FX, reconciliation and leverage show their working; '
      f'unresolved instruments and stale marks are flagged, never smoothed over.</p>'
      f'<p class="asof">Statements as of {AS_OF} · FX: {FX_SOURCE}, {FX_AS_OF}</p></section>')

recon_bad = [st for st in statements if not st.recon_ok]
s2 = slide("Overview", "Consolidated Position",
    f'<div class="grid4">'
    f'<div class="stat"><div class="lab">Gross assets</div><div class="big">{fmt(derived(gross,"USD","Σ holdings"))}</div>{datum(derived(gross,"USD","sum of parsed holdings, USD base"))}</div>'
    f'<div class="stat"><div class="lab">Liabilities</div><div class="big">{fmt(derived(debt,"USD",""))}</div>{datum(derived(debt,"USD","Lombard loan, Alpine Trust statement"))}</div>'
    f'<div class="stat"><div class="lab">Net worth</div><div class="big">{fmt(derived(net,"USD",""))}</div>{datum(derived(net,"USD","gross − liabilities"))}</div>'
    f'<div class="stat"><div class="lab">Leverage (debt/net)</div><div class="big">{debt/net:.1%}</div>{datum(derived(round(debt/net*100,1),"%","debt ÷ net worth"))}</div>'
    f'</div>'
    f'<p class="note">Reconciliation: {len(statements)-len(recon_bad)} of {len(statements)} custodians tie to their '
    f'stated total; {"none" if not recon_bad else ", ".join(st.custodian for st in recon_bad)} '
    f'{"" if not recon_bad else "shows a variance (see Data Quality)"}. Two legal entities '
    f'(individual + Holdco-2) consolidated to a USD base.</p>', n=1)

# Holdings by custodian
def holdings_table(st):
    rows = ""
    for p in st.positions:
        e = enrich.get(id(p))
        live = ""
        if e and e["price"].ok:
            live = f'<td class="num">{datum(e["price"])}</td>'
        elif e:
            live = f'<td class="num">{datum(e["price"])}</td>'
        else:
            live = '<td class="num cite">—</td>'
        fx = fx_fig(p.currency)
        fxcell = "USD" if p.currency == "USD" else f'{p.currency} @ {FX[p.currency]}'
        warn = "".join(f'<div class="warn">⚠ {f}</div>' for f in p.flags)
        rows += (f'<tr><td>{p.name}<br><span class="cite">{p.asset_class} · {p.instrument_type}'
                 f'{"" if p.resolved else " · UNRESOLVED ID"}</span>{warn}</td>'
                 f'<td class="cite">{fxcell}</td>'
                 f'<td class="num">{datum(stmt_fig(p.mv_base, p.custodian, p.val_as_of))}</td>'
                 f'{live}</tr>')
    total = sum(p.mv_base for p in st.positions)
    rec = ('<span style="color:var(--ok)">ties out</span>' if st.recon_ok
           else f'<span class="warn">Δ ${st.recon_delta:,.2f}</span>')
    rows += (f'<tr class="tot"><td>Parsed total</td><td></td>'
             f'<td class="num">${total:,.2f}</td><td class="num">{rec}</td></tr>')
    return (f'<h3>{st.custodian} · {st.entity} · {st.account_class}</h3>'
            f'<div class="scroll"><table class="tbl"><thead><tr><th>Holding</th><th>Ccy</th>'
            f'<th class="num">Statement value (USD)</th><th class="num">Live price / check</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>')

s3 = slide("Holdings", "Holdings by Custodian",
           "".join(holdings_table(st) for st in statements)
           + '<p class="note">Statement value is the custodian\'s own mark (source + date shown). '
           'Where an instrument id resolves, today\'s live price is shown alongside as an '
           'independent check; unresolved house-codes and stale valuations are flagged inline.</p>', n=2)

# Allocation
arows = ""
for cls in sorted(alloc, key=lambda c: -alloc[c]):
    v = alloc[cls]
    banded = cls in profile.allocation_bands
    tag = "" if banded else ' <span class="warn">no band</span>'
    arows += (f'<tr><td>{cls}{tag}</td>'
              f'<td class="num">{datum(stmt_fig(v, "consolidated", AS_OF, "Σ class, USD base"))}</td>'
              f'<td class="num">{v/gross:.1%}</td></tr>')
s4 = slide("Allocation", "Current Allocation (by value)",
    f'<div class="scroll"><table class="tbl"><thead><tr><th>Asset class</th>'
    f'<th class="num">Value (USD)</th><th class="num">% of gross</th></tr></thead>'
    f'<tbody>{arows}<tr class="tot"><td>Gross</td><td class="num">${gross:,.0f}</td>'
    f'<td class="num">100.0%</td></tr></tbody></table></div>'
    f'<p class="note">Allocation is computed from parsed statement values, not a target. '
    f'Alternatives and real estate carry no allocation band in this profile — flagged on '
    f'the suitability slide, not silently treated as compliant.</p>', n=3)

# Data quality
dq_rows = []
for st in statements:
    if not st.recon_ok:
        dq_rows.append(("Reconciliation", f'{st.custodian}: parsed vs stated differ by ${st.recon_delta:,.2f} — likely accrued interest not itemised'))
    for p in st.positions:
        for f in p.flags:
            dq_rows.append(("Data flag", f'{p.name}: {f}'))
dq_html = "".join(f'<div class="flagrow"><span class="chip chip-flag">{k}</span>'
                  f'<span class="d">{v}</span></div>' for k, v in dq_rows)
s5 = slide("Data Quality", "Reconciliation & Data-Quality Flags",
    (dq_html or '<p class="note">No data-quality issues.</p>')
    + '<p class="note">These are surfaced, not silently corrected: an unresolved house-code '
    'means the instrument is not yet mapped to a securities master; a stale manual valuation '
    'means an illiquid mark predates today by more than a quarter; a reconciliation variance '
    'means parsed holdings don\'t sum to the custodian\'s own stated total. Each must be '
    'resolved before the book is treated as clean.</p>', n=4)

# Suitability
suit_html = "".join(
    f'<div class="flagrow">{chip(f.enforcement, f.enforcement)}'
    f'<span class="d">{f.detail}</span></div>' for f in suit)
s6 = slide("Suitability", "Suitability of the Actual Book",
    f'<p class="note" style="margin-top:0">Mandate: advisory · gate: '
    f'<strong>{worst_enforcement(suit)}</strong></p>{suit_html}'
    f'<p class="note">Run on the parsed consolidated book. The reciprocal band check catches '
    f'the unbanded alternatives / real-estate sleeves; concentration flags the single large '
    f'direct property. The Lombard loan is parsed and leverage computed ({debt/net:.1%}), '
    f'ready for a leverage/DV01 check the engine does not yet run.</p>', n=5)

# Provenance appendix
prov = (f'<p class="note" style="margin-top:0">Holding values: custodian statements '
        f'(as of {AS_OF}). FX: {FX_SOURCE} ({FX_AS_OF}) — a live FX feed is the production '
        f'source. Live prices / expense ratios: yfinance, where the instrument id resolves. '
        f'Reconciliation, leverage and weights: derived, formulas shown. Nothing on this deck '
        f'is model-recalled; unresolved and stale items are flagged rather than filled.</p>')
s7 = slide("Method", "Provenance & Method", prov, n=6)

slides = [s1, s2, s3, s4, s5, s6, s7]
BODY = STYLE + '<div class="wrap">' + "".join(slides) + '</div>'

with open("kadir_review.html", "w") as fh:
    fh.write(BODY)

resolved = sum(1 for p in positions if p.resolved)
print(f"wrote kadir_review.html · {len(positions)} positions · net ${net:,.0f} · "
      f"leverage {debt/net:.1%} · {resolved}/{len(positions)} ids resolved · "
      f"{sum(1 for st in statements if not st.recon_ok)} recon variance · gate {worst_enforcement(suit)}")
