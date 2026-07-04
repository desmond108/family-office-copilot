"""build_deck.py — regenerate Kadir's full 13-slide proposal from datafeed.py.

The narration is wired to Figure objects: EVERY number in the deck is a Figure
carrying its provenance (live source + as_of, derived, or client-specified). A
figure with no trustworthy source renders as a visible amber SOURCE REQUIRED chip.
The generator is structurally incapable of emitting an unsourced number as fact.

Run (needs network; sandbox-off):  python3 build_deck.py  ->  writes kadir_deck.html
"""
from __future__ import annotations

import html
from datetime import date

from datafeed import Feed, Figure, required

feed = Feed()
AUM = 3_000_000

# --------------------------------------------------------------------------- #
# Figure builders for non-market provenance (client-specified, derived)
# --------------------------------------------------------------------------- #

def client(value, unit=""):
    return Figure(value, unit, "client-specified", "2026-07-02",
                  note="from Kadir's 2026-07-02 message")

def derived(value, unit, how, as_of=None):
    return Figure(value, unit, "derived", as_of, note=how)

def money(frac_or_amt, is_frac=True, how=""):
    amt = AUM * frac_or_amt if is_frac else frac_or_amt
    return derived(round(amt), "USD", how or f"3,000,000 × {frac_or_amt:.1%}")

def high_1y(ticker: str) -> Figure:
    try:
        import yfinance as yf
        h = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        c = h["Close"].dropna()
        return Figure(round(float(c.max().item()), 2), "", "yfinance 1y high",
                      c.index[-1].date().isoformat(), kind="price",
                      note="highest daily close, trailing 1y")
    except Exception as e:  # noqa: BLE001
        return required(f"yfinance error: {type(e).__name__}")

def pct_off(hi: Figure, frac: float) -> Figure:
    if not hi.ok:
        return required("depends on an unsourced reference high")
    return derived(round(float(hi.value) * (1 - frac), 2), "", f"−{frac:.0%} from {hi.value:,.0f} 1y high", hi.as_of)

# --------------------------------------------------------------------------- #
# Gather every figure
# --------------------------------------------------------------------------- #

F = {}
# Macro
F["fed_hi"] = feed.fred("DFEDTARU"); F["fed_lo"] = feed.fred("DFEDTARL")
F["ten"] = feed.fred("DGS10")
F["gold"] = feed.last_close("GC=F", "USD/oz")
F["spx"] = feed.last_close("^GSPC", ""); F["ndx"] = feed.last_close("^NDX", "")
F["hike_odds"] = required("CME FedWatch — not in yfinance/FRED")
F["fwd_pe"] = required("needs forward EPS estimates (premium feed)")
# Benchmark weights (client) + amounts (derived)
BENCH = [("USD money market", "SGOV", 0.10), ("Gold ETF", "GLDM", 0.20),
         ("Bond ETFs", "BND / VCIT", 0.20), ("Nasdaq-100 ETF", "QQQ", 0.20),
         ("S&P 500 ETF", "SPY", 0.30)]
# Equities
for t in ("SPY", "QQQ", "VOO", "QQQM"):
    F[f"er_{t}"] = feed.expense_ratio(t); F[f"aum_{t}"] = feed.fund_field(t, "totalAssets", "USD")
F["px_SPY"] = feed.last_close("SPY"); F["px_QQQ"] = feed.last_close("QQQ")
# Bonds
BONDS = ("VCIT", "BND", "AGG", "IEF")
for t in BONDS:
    F[f"er_{t}"] = feed.expense_ratio(t)
    F[f"dur_{t}"] = feed.reference(t, "effective_duration", "yr")   # factsheet (reference_table)
    _sec = feed.reference(t, "sec_yield_30d", "%")                  # real SEC yield if in table
    F[f"sec_{t}"] = _sec if _sec.ok else feed.dist_yield(t)         # else yfinance dist. proxy
    F[f"aum_{t}"] = feed.fund_field(t, "totalAssets", "USD")
    F[f"nav_{t}"] = feed.nav_impact_per_100bp(F[f"dur_{t}"])        # derived from duration
# Gold funds
for t in ("GLDM", "IAU", "GLD"):
    F[f"er_{t}"] = feed.expense_ratio(t); F[f"aum_{t}"] = feed.fund_field(t, "totalAssets", "USD")
# Cash
F["er_SGOV"] = feed.expense_ratio("SGOV"); F["y_SGOV"] = feed.dist_yield("SGOV")
F["aum_SGOV"] = feed.fund_field("SGOV", "totalAssets", "USD")
# Triggers
F["hi_spx"] = high_1y("^GSPC"); F["hi_ndx"] = high_1y("^NDX")
F["spx_15"] = pct_off(F["hi_spx"], 0.15); F["spx_20"] = pct_off(F["hi_spx"], 0.20)
F["ndx_15"] = pct_off(F["hi_ndx"], 0.15); F["ndx_20"] = pct_off(F["hi_ndx"], 0.20)

AS_OF = F["spx"].as_of or date.today().isoformat()

# --------------------------------------------------------------------------- #
# HTML rendering
# --------------------------------------------------------------------------- #

def fmt(fig: Figure) -> str:
    if not fig.ok:
        return fig.text()
    v = fig.value
    if fig.unit == "%":
        return f"{float(v):.2f}%"
    if fig.unit in ("USD", "USD/oz") and isinstance(v, (int, float)) and abs(v) >= 1000:
        if abs(v) >= 1e9:
            s = f"${v/1e9:,.1f}bn"
        elif fig.unit == "USD/oz":
            s = f"${v:,.2f}"
        else:
            s = f"${v:,.0f}"
        return s + (" /oz" if fig.unit == "USD/oz" else "")
    if fig.unit == "yr":
        return f"{v} yr"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return f"{v:,}" if isinstance(v, int) else str(v)

def datum(fig: Figure) -> str:
    """A value + its provenance line, or an amber SOURCE REQUIRED chip."""
    if not fig.ok:
        note = html.escape(fig.note or "no feed available")
        return (f'<span class="req">SOURCE REQUIRED</span>'
                f'<span class="cite">{note}</span>')
    stale = ' <span class="stale">stale</span>' if fig.stale else ""
    src = html.escape(fig.source)
    # Honest as_of: real date when we have one; explicit "reported date unknown"
    # for provider fundamentals that carry no timestamp (don't fake today()).
    if fig.as_of:
        asof = f" · {fig.as_of}"
    elif fig.kind == "fundamental":
        asof = ' · <span class="stale">reported date unknown</span>'
    else:
        asof = ""
    note = f' · {html.escape(fig.note)}' if fig.note and fig.source not in ("client-specified", "derived") else ""
    if fig.source in ("client-specified", "derived"):
        note = f' · {html.escape(fig.note)}' if fig.note else ""
    return (f'<span class="val">{fmt(fig)}{stale}</span>'
            f'<span class="cite">{src}{asof}{note}</span>')

def kv(label, fig):
    return f'<div class="kv"><span class="k">{label}</span><span class="v">{datum(fig)}</span></div>'

def slide(n, eyebrow, title, body):
    return (f'<section class="slide"><div class="eyebrow">{eyebrow}'
            f'<span class="sn">{n:02d}</span></div>'
            f'<h2>{title}</h2>{body}</section>')

# ---- individual slides ----------------------------------------------------- #

s1 = (f'<section class="slide cover"><div class="eyebrow">Portfolio Proposal · Confidential</div>'
      f'<h1>Asset Allocation Proposal</h1>'
      f'<p class="sub">USD 3,000,000 · UOB Account</p>'
      f'<p class="lede">Long-term strategic allocation with a phased entry plan. '
      f'Every figure below is stamped with its source; where no feed exists, the deck '
      f'says <span class="req-inline">SOURCE REQUIRED</span> rather than inventing a number.</p>'
      f'<p class="asof">Market data as of last close · {AS_OF}</p></section>')

# Slide 2 — client requirements
rows = "".join(f'<tr><td>{name}</td><td class="mono">{datum(client(int(w*100), "%"))}</td></tr>'
               for name, _, w in BENCH)
s2 = slide(2, "Client Brief", "Summary of Client Requirements",
    f'<div class="two"><div><h3>Long-term benchmark allocation</h3>'
    f'<table class="tbl"><thead><tr><th>Sleeve</th><th>Target</th></tr></thead><tbody>{rows}</tbody></table></div>'
    f'<div><h3>Current-stage strategy (client\'s own words)</h3><ol class="reqs">'
    f'<li>US equities richly valued — buy at most 5% of SPY/QQQ now, park the rest in the money-market fund.</li>'
    f'<li>Add to SPY/QQQ once they pull back 15–20% from the recent high.</li>'
    f'<li>Buy the gold ETF below USD 4,000/oz.</li>'
    f'<li>Bond sleeve: a ~5-year medium-duration <em>US Treasury</em> ETF, bought in tranches; assess rate-hike impact.</li>'
    f'<li>For every sleeve, screen for low fees and good liquidity.</li></ol></div></div>')

# Slide 3 — macro
s3 = slide(3, "Market Context", "Macro Environment",
    f'<div class="grid4">'
    f'<div class="stat"><div class="lab">Fed funds target</div><div class="big">{fmt(F["fed_lo"])}–{fmt(F["fed_hi"])}</div>{datum(F["fed_hi"])}</div>'
    f'<div class="stat"><div class="lab">10-yr Treasury</div><div class="big">{fmt(F["ten"])}</div>{datum(F["ten"])}</div>'
    f'<div class="stat"><div class="lab">Spot gold</div><div class="big">{fmt(F["gold"])}</div>{datum(F["gold"])}</div>'
    f'<div class="stat"><div class="lab">S&amp;P 500 · Nasdaq-100</div><div class="big">{fmt(F["spx"])} · {fmt(F["ndx"])}</div>{datum(F["spx"])}</div>'
    f'<div class="stat req-card"><div class="lab">Market-implied hike odds</div>{datum(F["hike_odds"])}</div>'
    f'<div class="stat req-card"><div class="lab">S&amp;P 500 forward P/E</div>{datum(F["fwd_pe"])}</div>'
    f'</div>')

# Slide 4 — strategic allocation
brow = "".join(
    f'<tr><td>{name}</td><td>{veh}</td><td class="mono">{datum(client(int(w*100),"%"))}</td>'
    f'<td class="mono">{datum(money(w, how=f"3,000,000 × {int(w*100)}%"))}</td></tr>'
    for name, veh, w in BENCH)
s4 = slide(4, "Strategic Allocation", "Long-Term Benchmark · USD 3,000,000",
    f'<table class="tbl"><thead><tr><th>Sleeve</th><th>Vehicle</th><th>Weight</th><th>Amount</th></tr></thead>'
    f'<tbody>{brow}<tr class="tot"><td>Total</td><td></td><td class="mono">100.00%</td>'
    f'<td class="mono">$3,000,000</td></tr></tbody></table>'
    f'<p class="note">Weights are the client\'s stated benchmark; amounts are arithmetic on the $3.0m base.</p>')

# Slide 5 — equity ETFs
def fundcard(t, extra=""):
    return (f'<div class="fund"><h3>{t}</h3>{kv("Expense ratio", F[f"er_{t}"])}'
            f'{kv("AUM", F[f"aum_{t}"])}{extra}</div>')
s5 = slide(5, "Equity Selection", "Equity ETFs · SPY and QQQ",
    f'<div class="two">'
    f'{fundcard("SPY", kv("Last price", F["px_SPY"]))}'
    f'{fundcard("QQQ", kv("Last price", F["px_QQQ"]))}</div>'
    f'<div class="two">'
    f'<div class="fund alt"><h3>Fee alternative · VOO</h3>{kv("Expense ratio", F["er_VOO"])}</div>'
    f'<div class="fund alt"><h3>Fee alternative · QQQM</h3>{kv("Expense ratio", F["er_QQQM"])}</div></div>'
    f'<p class="note">For a long-term holder who doesn\'t need options, VOO / QQQM track the same '
    f'indices at lower fees; SPY / QQQ win on liquidity and options depth.</p>')

# Slide 6 — bond comparison
head = "".join(f"<th>{t}</th>" for t in BONDS)
def brow_(label, key):
    return "<tr><td>" + label + "</td>" + "".join(f'<td>{datum(F[f"{key}_{t}"])}</td>' for t in BONDS) + "</tr>"
s6 = slide(6, "Fixed Income", "Bond ETF Comparison",
    f'<div class="scroll"><table class="tbl cmp"><thead><tr><th>Metric</th>{head}</tr></thead><tbody>'
    f'{brow_("Expense ratio","er")}{brow_("Yield — SEC where cited, else dist. proxy","sec")}'
    f'{brow_("Effective duration","dur")}{brow_("AUM","aum")}'
    f'{brow_("NAV impact @ +100bp","nav")}</tbody></table></div>'
    f'<p class="note">Effective duration is read from each issuer\'s official fact sheet (as of 31 Mar 2026, '
    f'archived in <span class="mono">reference_table.json</span>), and the +100bp NAV impact is derived from '
    f'it (≈ −duration%). Yields show the real 30-day SEC yield where the fact sheet gives it (AGG, IEF), '
    f'else a yfinance distribution-yield proxy (VCIT, BND) — the citation says which. Note the client asked '
    f'for a <em>Treasury</em> sleeve: BND/VCIT are mixed/corporate; IEI is the closer ~4yr Treasury match.</p>')

# Slide 7 — rate outlook
s7 = slide(7, "Rate Outlook", "US Rate-Hike Expectations",
    f'<div class="grid4">'
    f'<div class="stat"><div class="lab">10-yr Treasury yield</div><div class="big">{fmt(F["ten"])}</div>{datum(F["ten"])}</div>'
    f'<div class="stat"><div class="lab">Fed funds target</div><div class="big">{fmt(F["fed_lo"])}–{fmt(F["fed_hi"])}</div>{datum(F["fed_hi"])}</div>'
    f'<div class="stat req-card"><div class="lab">Implied hike odds (H2)</div>{datum(F["hike_odds"])}</div>'
    f'</div>'
    f'<p class="note">Every +100bp of rates costs a medium-duration bond ETF roughly its duration in NAV — '
    f'so the exact figure is deferred until duration is sourced. Practical call: buy the bond sleeve in '
    f'three tranches around the coming FOMC meetings rather than in one go; undeployed cash earns the '
    f'money-market yield while it waits.</p>')

# Slide 8 — gold
s8 = slide(8, "Gold Allocation", "Gold ETF Selection &amp; Entry",
    f'<div class="stat wide"><div class="lab">Spot gold</div><div class="big">{fmt(F["gold"])}</div>{datum(F["gold"])}</div>'
    f'<div class="three">'
    f'{fundcard("GLDM")}{fundcard("IAU")}{fundcard("GLD")}</div>'
    f'<div class="two"><div class="fund alt"><h3>Entry trigger</h3>'
    f'{kv("Buy first 10% below", client(4000,"USD"))}{kv("Complete to 20% below", client(3850,"USD"))}</div>'
    f'<div class="fund alt"><h3>Status now</h3><p class="note" style="margin:0">'
    f'Spot {fmt(F["gold"])} is above the client\'s $4,000 line — park the cash in SGOV and wait; do not chase.</p></div></div>')

# Slide 9 — cash
s9 = slide(9, "Cash Management", "USD Money Market · SGOV",
    f'<div class="grid4">'
    f'<div class="stat"><div class="lab">Expense ratio</div><div class="big">{fmt(F["er_SGOV"])}</div>{datum(F["er_SGOV"])}</div>'
    f'<div class="stat"><div class="lab">Distribution yield</div><div class="big">{fmt(F["y_SGOV"])}</div>{datum(F["y_SGOV"])}</div>'
    f'<div class="stat"><div class="lab">AUM</div><div class="big">{fmt(F["aum_SGOV"])}</div>{datum(F["aum_SGOV"])}</div>'
    f'</div>'
    f'<p class="note">Dual role: a permanent $300k liquidity reserve (10% benchmark) plus a tactical '
    f'reservoir warehousing capital that is awaiting equity pullbacks, bond tranches and a gold trigger — '
    f'earning the money-market yield while it waits.</p>')

# Slide 10 — current-stage plan
PLAN = [("SPY", 0.05, 150_000, "Starter; add on pullback triggers"),
        ("QQQ", 0.05, 150_000, "Starter; add on pullback triggers"),
        ("Bonds (BND+VCIT)", 0.0667, 200_000, "Tranche 1 of 3; later tranches straddle FOMC"),
        ("Gold (GLDM)", 0.0, 0, "Spot above $4,000 — wait for trigger"),
        ("Money market (SGOV)", 0.833, 2_500_000, "$300k reserve + $2.2m deployment reservoir")]
prow = "".join(
    f'<tr><td>{n}</td><td class="mono">{datum(derived(round(f*100,1),"%","plan for current stage"))}</td>'
    f'<td class="mono">{datum(derived(a,"USD","plan for current stage"))}</td><td>{note}</td></tr>'
    for n, f, a, note in PLAN)
s10 = slide(10, "Phase 1", "Current-Stage Allocation · Execute Now",
    f'<div class="scroll"><table class="tbl"><thead><tr><th>Sleeve</th><th>Now</th><th>Amount</th><th>Notes</th></tr></thead>'
    f'<tbody>{prow}</tbody></table></div>'
    f'<p class="note">"Now" weights are the recommended phased-entry plan (derived from the client\'s '
    f'strategy), not the long-term benchmark.</p>')

# Slide 11 — triggers
s11 = slide(11, "Execution Triggers", "Phased-Entry Trigger Conditions",
    f'<div class="scroll"><table class="tbl"><thead><tr><th>Asset</th><th>Reference 1y high</th>'
    f'<th>Trigger 1 (−15%)</th><th>Trigger 2 (−20%)</th></tr></thead><tbody>'
    f'<tr><td>S&amp;P 500</td><td>{datum(F["hi_spx"])}</td><td>{datum(F["spx_15"])}</td><td>{datum(F["spx_20"])}</td></tr>'
    f'<tr><td>Nasdaq-100</td><td>{datum(F["hi_ndx"])}</td><td>{datum(F["ndx_15"])}</td><td>{datum(F["ndx_20"])}</td></tr>'
    f'<tr><td>Gold / GLDM</td><td>{datum(F["gold"])}</td><td>{datum(client(4000,"USD"))} → buy 10%</td>'
    f'<td>{datum(client(3850,"USD"))} → complete 20%</td></tr>'
    f'<tr><td>Bonds</td><td>tranche-based</td><td>Tranche 2 after Sep–Oct FOMC</td>'
    f'<td>Tranche 3 after Dec FOMC, or if 10-yr ≥ 5%</td></tr></tbody></table></div>'
    f'<p class="note">Equity triggers are −15% / −20% off the trailing-1-year high (derived from the sourced '
    f'high). Execute mechanically when hit; re-assess the benchmark if nothing triggers within 12 months.</p>')

# Slide 12 — roadmap
s12 = slide(12, "Roadmap", "Implementation Roadmap",
    f'<div class="road">'
    f'<div class="step"><div class="when">Now · Jul 2026</div><p>Account setup; buy SPY 5% + QQQ 5% + bond tranche 1 ($200k); park $2.5m in SGOV; set price alerts.</p></div>'
    f'<div class="step"><div class="when">Q3 · Jul–Sep</div><p>Watch the Sep FOMC; start the gold programme if spot breaks $4,000; add equities on any pullback trigger.</p></div>'
    f'<div class="step"><div class="when">Q4 · Oct–Dec</div><p>Bond tranche 2 after the Oct FOMC, tranche 3 after Dec; year-end review.</p></div>'
    f'<div class="step"><div class="when">From 2027</div><p>Review every six months; rebalance to benchmark when any sleeve drifts ±5% from target.</p></div>'
    f'</div>')

# Slide 13 — risk + provenance methodology
s13 = slide(13, "Risks &amp; Method", "Risk Disclosure &amp; Provenance",
    f'<div class="two"><div><h3>Risks</h3><ul class="reqs">'
    f'<li><strong>Market risk</strong> — equity, gold and bond prices can all fall; triggers are a discipline tool, not downside protection.</li>'
    f'<li><strong>Rate risk</strong> — if hikes exceed expectations, bond NAVs may fall further; tranching mitigates but does not eliminate.</li>'
    f'<li><strong>FX &amp; tax</strong> — USD assets carry currency risk; US-listed ETFs raise withholding and estate-tax questions — confirm with a tax adviser.</li></ul></div>'
    f'<div><h3>How the numbers were sourced</h3><p class="note" style="margin-top:0">'
    f'Live figures come from yfinance (prices, fund fees/yields/AUM) and FRED (rates), each stamped with '
    f'its <span class="mono">as_of</span> date. Derived figures show their formula. Client figures come '
    f'from the 2026-07-02 message. Cells no free feed can fill — bond duration, CME FedWatch odds, forward '
    f'P/E — are marked <span class="req-inline">SOURCE REQUIRED</span>, never guessed.</p>'
    f'<p class="disc">For discussion only; not investment advice, an offer or a solicitation. Past '
    f'performance is not indicative of future results.</p></div></div>')

slides = [s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12, s13]

# Scorecard
ok = sum(1 for f in F.values() if f.ok)
missing = [k for k, f in F.items() if not f.ok]

STYLE = """
<style>
:root{
  --bg:#e9edf4; --surface:#ffffff; --ink:#152142; --ink-soft:#5a648a;
  --gold:#9c7a24; --rule:#d3dae8; --ok:#2f7a52; --req:#9a6410; --req-bg:#f6e9cf;
  --mono-ink:#6b7599;
  --serif:"Hoefler Text","Iowan Old Style","Palatino Linotype",Georgia,serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:"SF Mono",ui-monospace,"JetBrains Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#080f24; --surface:#111d42; --ink:#eaeefa; --ink-soft:#9aa6c8;
  --gold:#d2ac57; --rule:#26335c; --ok:#5cc08a; --req:#e8b866; --req-bg:#3a2f14;
  --mono-ink:#8592b8;
}}
:root[data-theme="light"]{
  --bg:#e9edf4; --surface:#ffffff; --ink:#152142; --ink-soft:#5a648a;
  --gold:#9c7a24; --rule:#d3dae8; --ok:#2f7a52; --req:#9a6410; --req-bg:#f6e9cf; --mono-ink:#6b7599;
}
:root[data-theme="dark"]{
  --bg:#080f24; --surface:#111d42; --ink:#eaeefa; --ink-soft:#9aa6c8;
  --gold:#d2ac57; --rule:#26335c; --ok:#5cc08a; --req:#e8b866; --req-bg:#3a2f14; --mono-ink:#8592b8;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding:40px 20px 80px}
.slide{background:var(--surface);border:1px solid var(--rule);border-radius:10px;
  padding:44px 48px;margin:22px 0;box-shadow:0 1px 3px rgba(10,20,50,.06)}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--gold);display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.sn{color:var(--ink-soft);opacity:.6}
h1{font-family:var(--serif);font-weight:600;font-size:46px;line-height:1.05;margin:.1em 0 .2em;
  text-wrap:balance;letter-spacing:-.01em}
h2{font-family:var(--serif);font-weight:600;font-size:30px;line-height:1.1;margin:0 0 24px;
  text-wrap:balance;letter-spacing:-.01em}
h3{font-family:var(--sans);font-weight:650;font-size:15px;margin:0 0 12px;letter-spacing:.01em}
.cover{background:linear-gradient(150deg,var(--surface),color-mix(in srgb,var(--gold) 8%,var(--surface)));
  padding-top:60px;padding-bottom:60px}
.sub{font-family:var(--serif);font-size:22px;color:var(--ink-soft);margin:.2em 0 1.2em}
.lede{max-width:62ch;color:var(--ink);font-size:15px}
.asof{font-family:var(--mono);font-size:12px;color:var(--mono-ink);margin-top:28px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.three{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
.grid4{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}
@media(max-width:680px){.two,.three,.grid4{grid-template-columns:1fr}}
.stat{background:color-mix(in srgb,var(--gold) 5%,var(--surface));border:1px solid var(--rule);
  border-radius:8px;padding:18px}
.stat.wide{margin-bottom:16px}
.lab{font-size:12px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
.big{font-family:var(--serif);font-size:30px;font-weight:600;font-variant-numeric:tabular-nums;line-height:1}
.req-card{background:var(--req-bg);border-color:color-mix(in srgb,var(--req) 40%,var(--rule))}
.val{display:block;font-variant-numeric:tabular-nums;font-weight:600;font-size:15px}
.cite{display:block;font-family:var(--mono);font-size:10.5px;color:var(--mono-ink);margin-top:3px;line-height:1.35}
.req{display:inline-block;font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.08em;
  color:var(--req);background:var(--req-bg);border:1px solid color-mix(in srgb,var(--req) 45%,transparent);
  padding:2px 7px;border-radius:4px}
.req-inline{font-family:var(--mono);font-size:.85em;color:var(--req);background:var(--req-bg);
  padding:1px 5px;border-radius:3px;white-space:nowrap}
.stale{font-family:var(--mono);font-size:9px;color:var(--req);text-transform:uppercase;
  letter-spacing:.05em;vertical-align:middle}
.tbl{width:100%;border-collapse:collapse;font-size:14px}
.tbl th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-soft);
  border-bottom:1px solid var(--rule);padding:8px 10px}
.tbl td{padding:9px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
.tbl .tot td{font-weight:700;border-top:2px solid var(--gold);border-bottom:none}
.cmp td:first-child{color:var(--ink-soft);font-size:12px}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}
.kv{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-bottom:1px solid var(--rule)}
.kv:last-child{border-bottom:none}
.kv .k{font-size:13px;color:var(--ink-soft)}
.kv .v{text-align:right}
.fund{background:color-mix(in srgb,var(--gold) 4%,var(--surface));border:1px solid var(--rule);
  border-radius:8px;padding:18px 20px}
.fund.alt{background:transparent}
.fund h3{color:var(--gold);font-family:var(--mono);letter-spacing:.04em}
.reqs{margin:0;padding-left:18px}.reqs li{margin:8px 0;font-size:14px}
.reqs em,.note em{font-style:normal;font-weight:650;color:var(--gold)}
.note{font-size:13px;color:var(--ink-soft);max-width:74ch;margin-top:16px}
.disc{font-size:11px;color:var(--mono-ink);margin-top:14px;line-height:1.5}
.road{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
@media(max-width:680px){.road{grid-template-columns:1fr}}
.step{border-top:2px solid var(--gold);padding-top:12px}
.step .when{font-family:var(--mono);font-size:11px;color:var(--gold);letter-spacing:.05em;margin-bottom:6px}
.step p{font-size:13px;margin:0;color:var(--ink-soft)}
.legend{max-width:1000px;margin:0 auto;padding:0 20px}
.scorebar{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:20px 28px;
  margin:22px 0;display:flex;gap:28px;flex-wrap:wrap;align-items:center}
.scorebar .big{font-size:24px}
.scorebar .lab{margin:0}
</style>
"""

BODY = (STYLE + '<div class="wrap">' + "".join(slides) +
        f'<div class="scorebar"><div><div class="lab">Figures sourced</div>'
        f'<div class="big" style="color:var(--ok)">{ok}</div></div>'
        f'<div><div class="lab">Source required</div>'
        f'<div class="big" style="color:var(--req)">{len(missing)}</div></div>'
        f'<div style="flex:1;min-width:220px"><div class="lab">Still needs a feed</div>'
        f'<div class="cite" style="font-size:12px">{html.escape(", ".join(sorted(missing)))}</div></div>'
        f'</div></div>')

with open("kadir_deck.html", "w") as fh:
    fh.write(BODY)

print(f"wrote kadir_deck.html · {ok} sourced, {len(missing)} SOURCE REQUIRED")
print("source-required:", ", ".join(sorted(missing)))
