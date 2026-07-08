"""proposal_deck.py — the USD-3,000,000 proposal rendered as inline HTML slides.

This reproduces the layout of ``Portfolio_Proposal_USD3M_English.pdf`` (the navy /
gold house deck) as a self-contained HTML string so the Streamlit Proposal page can
show *exactly* what the downloadable PPTX / PDF contain. Content is the polished
USD-3.0m example; the two download buttons on the page serve the real files.

No network, no dependencies — just a string builder.  ``deck_html()`` returns the
full page; the app renders it with ``st.components.v1.html``.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- #
# House style — navy slides on light stock, gold accents (matches the PDF)
# --------------------------------------------------------------------------- #
STYLE = """
<style>
:root{
  --navy:#1e2a56; --navy-2:#22306a; --ink:#1e2a56; --soft:#5a648a;
  --gold:#c19a2e; --gold-ink:#b0872a; --rule:#dfe4ef; --card:#f4f6fb;
  --ok:#2f7a52; --warn:#b3402f; --page:#ffffff;
  --serif:"Iowan Old Style","Palatino Linotype",Georgia,serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:"SF Mono",ui-monospace,Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html,body{margin:0;background:#e9edf4;color:var(--ink);
  font-family:var(--sans);-webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto;padding:16px 12px 60px}
.slide{background:var(--page);border:1px solid var(--rule);border-radius:10px;
  padding:40px 46px;margin:16px 0;box-shadow:0 1px 4px rgba(20,30,70,.07);
  min-height:500px;position:relative}
.eyebrow{font-family:var(--sans);font-size:11px;font-weight:700;letter-spacing:.22em;
  text-transform:uppercase;color:var(--gold-ink);margin-bottom:14px}
h1{font-family:var(--sans);font-weight:800;font-size:46px;line-height:1.03;
  margin:.1em 0 .3em;letter-spacing:-.02em;color:var(--navy)}
h2{font-family:var(--sans);font-weight:800;font-size:31px;line-height:1.08;
  margin:0 0 26px;letter-spacing:-.02em;color:var(--navy)}
h3{font-weight:700;font-size:15px;margin:0 0 12px;color:var(--navy)}
.cover{background:linear-gradient(140deg,#1e2a56 0%,#22306a 60%,#2a3a7e 100%);
  color:#fff;overflow:hidden}
.cover .eyebrow{color:#c8a24a}
.cover h1{color:#fff}
.cover .blob{position:absolute;border-radius:50%;background:rgba(255,255,255,.05)}
.cover .b1{width:300px;height:300px;right:-70px;top:-90px}
.cover .b2{width:230px;height:230px;right:60px;bottom:-120px;background:rgba(255,255,255,.04)}
.sub{font-size:22px;font-weight:600;color:#c9d2ea;margin:.1em 0 2.4em;position:relative}
.lede{max-width:60ch;color:#aeb8d6;font-size:14px;line-height:1.6;position:relative}
.stamp{font-weight:700;color:#c8a24a;margin-top:34px;position:relative}
.two{display:grid;grid-template-columns:1fr 1fr;gap:26px}
.two.tilt{grid-template-columns:340px 1fr}
.three{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:640px){.two,.two.tilt,.three,.grid2{grid-template-columns:1fr}}
.navycard{background:var(--navy);color:#fff;border-radius:10px;padding:26px 28px}
.navycard h3{color:#c8a24a}
.navycard .row{display:flex;justify-content:space-between;align-items:center;
  padding:13px 0;border-bottom:1px solid rgba(255,255,255,.12);font-size:15px}
.navycard .row:last-child{border-bottom:none}
.navycard .row b{color:#c8a24a;font-size:17px;font-variant-numeric:tabular-nums}
.stat{background:var(--card);border:1px solid var(--rule);border-radius:9px;padding:22px 24px}
.stat .lab{font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--gold-ink);
  text-transform:uppercase;margin-bottom:8px}
.stat .big{font-family:var(--sans);font-size:34px;font-weight:800;color:var(--navy);
  line-height:1;letter-spacing:-.02em;margin-bottom:12px;font-variant-numeric:tabular-nums}
.stat p{font-size:13px;color:var(--soft);margin:0;line-height:1.5}
.reqs{list-style:none;margin:0;padding:0;counter-reset:r}
.reqs li{position:relative;padding:0 0 18px 40px;counter-increment:r;font-size:14px;
  color:var(--soft);line-height:1.5}
.reqs li::before{content:counter(r);position:absolute;left:0;top:-2px;width:26px;height:26px;
  background:var(--gold);color:#fff;border-radius:50%;font-weight:700;font-size:13px;
  display:flex;align-items:center;justify-content:center}
.reqs li b{color:var(--navy)}
.tbl{width:100%;border-collapse:collapse;font-size:13.5px}
.tbl th{background:var(--navy);color:#fff;text-align:left;font-size:12px;font-weight:700;
  padding:11px 12px}
.tbl th:first-child{border-radius:6px 0 0 0}.tbl th:last-child{border-radius:0 6px 0 0}
.tbl td{padding:11px 12px;border-bottom:1px solid var(--rule);vertical-align:top;color:var(--ink)}
.tbl tr:last-child td{border-bottom:none}
.tbl .tot td{font-weight:800;border-top:2px solid var(--gold);background:var(--card)}
.tbl .metric{color:var(--soft);font-weight:600}
.tbl .rec{background:#f7f3e6}
.good{color:var(--ok);font-weight:700}.bad{color:var(--warn);font-weight:700}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.center{text-align:center}
.note{font-size:12.5px;color:var(--soft);margin-top:20px;line-height:1.55;max-width:78ch}
.note b{color:var(--navy)}
.fundcard{border-radius:10px;padding:24px 26px}
.fundcard.solid{background:var(--navy);color:#fff}
.fundcard.solid .k,.fundcard.solid h3{color:#fff}
.fundcard.solid .g{color:#c8a24a}
.fundcard.ghost{background:var(--card);border:1px solid var(--rule)}
.fundcard h3{font-size:17px;margin-bottom:4px}
.fundcard .tag{color:var(--gold-ink);font-weight:700;font-size:14px;margin-bottom:16px;display:block}
.fundcard .k{display:block;color:var(--gold-ink);font-weight:700;font-size:13px;margin-top:14px}
.fundcard .v{font-size:13.5px;line-height:1.5}
.donut{width:200px;height:200px;border-radius:50%;
  background:conic-gradient(#1e2a56 0 30%,#5a6cae 30% 50%,#c19a2e 50% 70%,
    #8f9bcb 70% 90%,#aeb6cf 90% 100%);
  -webkit-mask:radial-gradient(circle 56px at center,transparent 98%,#000 100%);
          mask:radial-gradient(circle 56px at center,transparent 98%,#000 100%);
  margin:6px auto}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;justify-content:center;margin-top:16px;
  font-size:12px;color:var(--soft)}
.legend i{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:6px;
  vertical-align:middle}
.road{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:10px}
@media(max-width:640px){.road{grid-template-columns:1fr}}
.step{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:20px}
.step.solid{background:var(--navy);color:#fff}
.step.solid p,.step.solid .st-t{color:#cdd5ee}
.step .n{width:30px;height:30px;border-radius:50%;background:var(--navy);color:#fff;
  font-weight:800;display:flex;align-items:center;justify-content:center;margin-bottom:14px}
.step.solid .n{background:var(--gold)}
.step .when{color:var(--gold-ink);font-weight:700;font-size:12px;margin-bottom:8px}
.step .st-t{font-weight:800;color:var(--navy);font-size:15px;margin-bottom:10px}
.step p{font-size:12.5px;color:var(--soft);margin:0;line-height:1.5}
.foot{position:absolute;left:46px;bottom:16px;font-size:10.5px;color:#9aa4c4}
.pageno{position:absolute;right:46px;bottom:16px;font-size:10.5px;color:#9aa4c4}
</style>
"""

FOOT = ('<div class="foot">Portfolio Proposal · July 2026 · Confidential</div>'
        '<div class="pageno">{n}</div>')


def _slide(n, eyebrow, title, body, cover=False):
    if cover:
        return (f'<section class="slide cover"><span class="blob b1"></span>'
                f'<span class="blob b2"></span>{body}</section>')
    return (f'<section class="slide"><div class="eyebrow">{eyebrow}</div>'
            f'<h2>{title}</h2>{body}{FOOT.format(n=n)}</section>')


def deck_html() -> str:
    # ---- Slide 1 · cover -------------------------------------------------- #
    s1 = _slide(1, "", "", (
        '<div class="eyebrow">Portfolio Proposal · Confidential</div>'
        '<h1>Asset Allocation Proposal</h1>'
        '<div class="sub">USD 3,000,000 Portfolio · UOB Account</div>'
        '<div class="lede">Long-term strategic allocation + phased entry plan for the '
        'current stage<br>Tailored to client requirements · Data as of July 1, 2026</div>'
        '<div class="stamp">July 2026</div>'), cover=True)

    # ---- Slide 2 · client requirements ------------------------------------ #
    bench = [("USD money market fund", "10%"), ("Gold ETF", "20%"), ("Bond fund", "20%"),
             ("Nasdaq-100 ETF", "20%"), ("S&P 500 ETF", "30%")]
    brows = "".join(f'<div class="row"><span>{n}</span><b>{w}</b></div>' for n, w in bench)
    reqs = [
        ("Valuation", "US equities are richly valued; buy at most an initial 5% of the "
         "Nasdaq-100 / S&P 500 ETFs (or none), parking the rest in the USD money market fund"),
        ("Buy the dip", "Consider buying once the Nasdaq-100 or S&P 500 pulls back 15%–20% "
         "from its recent high"),
        ("Gold trigger", "The gold ETF may be bought below USD 4,000/oz"),
        ("Bond approach", "Consider a ~5-year medium-duration US Treasury ETF, bought in "
         "tranches; assess the impact of US rate-hike expectations"),
        ("Screening", "For every asset class, select products with low fees and good liquidity"),
    ]
    rl = "".join(f'<li><b>{h}</b>&nbsp; {t}</li>' for h, t in reqs)
    s2 = _slide(2, "Client Brief", "Summary of Client Requirements", (
        '<div class="two tilt">'
        f'<div class="navycard"><h3>1 · Long-Term Benchmark Allocation</h3>{brows}</div>'
        f'<div><h3>2 · Current-Stage Operating Strategy '
        f'<span style="color:#5a648a;font-weight:600">(client\'s original requests)</span></h3>'
        f'<ol class="reqs">{rl}</ol></div></div>'))

    # ---- Slide 3 · macro -------------------------------------------------- #
    def stat(lab, big, p):
        return f'<div class="stat"><div class="lab">{lab}</div><div class="big">{big}</div><p>{p}</p></div>'
    s3 = _slide(3, "Market Context", "Macro Environment (Mid-2026)", (
        '<div class="grid2">'
        + stat("Fed funds target range", "3.50–3.75%",
               "Held at the June FOMC; new Chair Warsh leans hawkish and the easing bias "
               "has been removed")
        + stat("Market-implied odds of 2026 H2 hikes", "73–88%",
               "CME FedWatch: ~73% Sep, ~81% Oct, ~88% Dec; BofA forecasts +75bp to "
               "4.25–4.50% by year-end")
        + stat("Spot gold price (USD/oz)", "$4,067",
               "Pulling back from highs — only ~1.7% above the client's $4,000 buy line, "
               "in its weakest quarter in 13 years")
        + stat("S&P 500 forward P/E", "20.1x",
               "Above the 10-yr average of 19.0x; index ~7,440; Nasdaq-100 hit a record "
               "~30,660 in early June")
        + '</div>'))

    # ---- Slide 4 · strategic allocation ----------------------------------- #
    arows = [("S&P 500 ETF", "SPY", "30%", "900,000"),
             ("Nasdaq-100 ETF", "QQQ", "20%", "600,000"),
             ("Bond ETFs", "BND / VCIT", "20%", "600,000"),
             ("Gold ETF", "GLDM (or IAU)", "20%", "600,000"),
             ("USD money market", "SGOV (0–3M T-bill ETF)", "10%", "300,000")]
    ar = "".join(f'<tr><td>{a}</td><td>{v}</td><td class="mono">{w}</td>'
                 f'<td class="mono">{amt}</td></tr>' for a, v, w, amt in arows)
    leg = [("S&P 500 (SPY)", "#1e2a56"), ("Nasdaq-100 (QQQ)", "#5a6cae"),
           ("Bond ETFs", "#c19a2e"), ("Gold ETF", "#8f9bcb"), ("Money market", "#aeb6cf")]
    legend = "".join(f'<span><i style="background:{c}"></i>{n}</span>' for n, c in leg)
    s4 = _slide(4, "Strategic Allocation", "Long-Term Benchmark: USD 3,000,000", (
        '<div class="two">'
        f'<div class="center"><div class="donut"></div><div class="legend">{legend}</div></div>'
        f'<div><table class="tbl"><tr><th>Asset class</th><th>Recommended vehicle</th>'
        f'<th>Weight</th><th>Amount (USD)</th></tr>{ar}'
        f'<tr class="tot"><td>Total</td><td></td><td class="mono">100%</td>'
        f'<td class="mono">3,000,000</td></tr></table></div></div>'
        '<p class="note">The 50/20/20/10 equity / bond / gold / cash structure balances growth, '
        'income and defence; the 50% equity sleeve is the portfolio\'s primary long-term '
        'return driver.</p>'))

    # ---- Slide 5 · equity ETFs -------------------------------------------- #
    def eq(cls, name, tag, index, er, liq, role):
        return (f'<div class="fundcard {cls}"><h3>{name}</h3><span class="tag">{tag}</span>'
                f'<span class="k">Index</span><div class="v">{index}</div>'
                f'<span class="k">Expense ratio</span><div class="v">{er}</div>'
                f'<span class="k">Liquidity</span><div class="v">{liq}</div>'
                f'<span class="k">Role</span><div class="v">{role}</div></div>')
    s5 = _slide(5, "Equity Selection", "Equity ETFs: SPY and QQQ", (
        '<div class="two">'
        + eq("solid", "SPY · SPDR S&P 500 ETF", "30% · $900,000", "S&P 500 (500 US large caps)",
             "0.0945%", "The world's most heavily traded ETF; razor-thin spreads and the "
             "deepest options market", "Core growth engine with broad sector diversification")
        + eq("ghost", "QQQ · Invesco Nasdaq-100 ETF", "20% · $600,000",
             "Nasdaq-100 (tech / growth leaders)", "0.20%",
             "Second most active broad-market ETF globally; excellent options liquidity",
             "Captures the AI / technology growth theme; higher volatility than SPY")
        + '</div>'
        '<p class="note"><b>Fee optimisation:</b> For a long-term holder who doesn\'t need '
        'options, VOO (0.03%) can replace SPY and QQQM (0.15%) can replace QQQ — same indices, '
        'lower fees; SPY / QQQ win on liquidity and execution.</p>'))

    # ---- Slide 6 · bond comparison ---------------------------------------- #
    cols = ["VCIT", "BND", "AGG", "IEF"]
    bdata = [
        ("Holdings", ["IG corporate bonds (5–10 yr)", "Total IG bond market (Tsy + corp + MBS)",
                      "Total IG bond market (Tsy + corp + MBS)", "US Treasuries only (7–10 yr)"]),
        ("Expense ratio", ['<span class="good">0.03%</span>', '<span class="good">0.03%</span>',
                           '<span class="good">0.03%</span>', "0.15%"]),
        ("30-day SEC yield", ['<span class="good">≈4.75%</span>', "≈3.94%", "≈3.9%", "≈4.29%"]),
        ("Effective duration", ["≈6.2 yr", "≈6.0 yr", "≈6.0 yr", '<span class="bad">≈7.0 yr</span>']),
        ("Credit risk", ["Yes (corporates)", "Low (diversified)", "Low (diversified)",
                         '<span class="good">None (Treasuries)</span>']),
        ("Liquidity", ["Very good", "Excellent", "Excellent", "Excellent"]),
        ("Est. NAV impact, rates +100bp", ["≈ -6.2%", "≈ -6.0%", "≈ -6.0%",
                                           '<span class="bad">≈ -7.0%</span>']),
    ]
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = ""
    for metric, vals in bdata:
        body += (f'<tr><td class="metric">{metric}</td>'
                 + "".join(f"<td>{v}</td>" for v in vals) + "</tr>")
    s6 = _slide(6, "Fixed Income", "Bond ETF Comparison: VCIT / BND / AGG / IEF", (
        f'<table class="tbl"><tr><th>Metric</th>{head}</tr>{body}</table>'
        '<p class="note"><b>Conclusion:</b> Balancing cost, yield and diversification, we '
        'recommend BND as the core (~12%) plus VCIT for yield enhancement (~8%). For a '
        'pure-Treasury sleeve choose IEF, noting its ~7-yr duration is more volatile in a '
        'hiking cycle. All four run longer than the client\'s 5-yr target — for a strict match '
        'to a "5-yr medium-duration Treasury", consider IEI (3–7 yr Treasuries, '
        'duration ≈4.3 yr, yield ≈3.76%).</p>'))

    # ---- Slide 7 · rate outlook ------------------------------------------- #
    left = (
        '<div class="stat" style="height:100%"><h3>The rate regime has flipped from cuts to hikes</h3>'
        '<ul style="margin:14px 0 0;padding-left:18px;color:#5a648a;font-size:13.5px;line-height:1.7">'
        '<li>After 175bp of cuts in 2024–2025, the Fed turned hawkish in 2026: the easing bias '
        'was removed at the June meeting, with inflation still above the 2% target on Middle '
        'East tensions and energy prices</li>'
        '<li>Futures pricing: ~73% odds of a September hike; policy rate near ~4% by year-end; '
        'BofA forecasts +75bp to 4.25–4.50%</li>'
        '<li>The 10-year Treasury yield has risen to ~4.7%, the highest since May 2025</li>'
        '</ul></div>')
    right_items = [
        ("Near-term NAV pressure", "Every +100bp in rates costs a medium-duration bond ETF "
         "roughly 6–7% of NAV — do not deploy in one go"),
        ("Tranching is the right call", "Buy in 3 tranches of ~$200k each, straddling the "
         "Sep / Oct / Dec FOMC meetings; once hikes land, yields — and entry points — are better"),
        ("Waiting is paid", "Undeployed cash parked in SGOV earns ~3.5–3.9% annualised, and "
         "money-market yields rise further if the Fed hikes"),
    ]
    ri = "".join(f'<div style="margin-bottom:16px"><div class="g" style="color:#c8a24a;'
                 f'font-weight:700;margin-bottom:4px">{h}</div>'
                 f'<div style="font-size:13px;color:#cdd5ee;line-height:1.5">{t}</div></div>'
                 for h, t in right_items)
    s7 = _slide(7, "Rate Outlook", "US Rate-Hike Expectations (Client Question 4)", (
        '<div class="two">' + left
        + f'<div class="navycard"><h3>Three implications for bond entry</h3>{ri}</div></div>'))

    # ---- Slide 8 · gold --------------------------------------------------- #
    grows = [("Expense ratio", ['<span class="good">0.10%</span>', "0.25%", "0.40%"]),
             ("AUM", ["≈$27.6bn", "≈$61bn", "≈$141.7bn"]),
             ("Liquidity", ["Good", "Very good", "Deepest"]),
             ("Best for", ["Long-term hold, lowest cost", "Cost / liquidity balance",
                           "Large, frequent trades / options"])]
    gh = "".join(f'<tr><td class="metric">{m}</td>'
                 + "".join(f'<td>{v}</td>' for v in vs) + "</tr>" for m, vs in grows)
    s8 = _slide(8, "Gold Allocation", "Gold ETF Selection and Entry Timing", (
        '<div class="two">'
        f'<div><table class="tbl"><tr><th>Metric</th><th>GLDM (rec.)</th><th>IAU</th>'
        f'<th>GLD</th></tr>{gh}</table>'
        f'<p class="note">All three hold physical bullion tracking the LBMA gold price with '
        f'≈1.00 correlation; for a long-term hold the fee gap drives net returns — hence GLDM.</p></div>'
        '<div class="navycard"><h3>Entry timing</h3>'
        '<div class="big" style="font-size:38px;font-weight:800;margin:6px 0 12px">$4,067</div>'
        '<div style="font-size:13px;color:#cdd5ee;line-height:1.5;margin-bottom:14px">'
        'Current gold price (USD/oz) — only ~1.7% above the client\'s $4,000 buy line</div>'
        '<ul style="margin:0;padding-left:18px;font-size:13px;color:#cdd5ee;line-height:1.7">'
        '<li>Below $4,000: buy first 10% ($300k)</li>'
        '<li>Below $3,850: complete the 20% ($600k)</li>'
        '<li>If gold stays above $4,000, park the cash in SGOV and wait — do not chase</li>'
        '</ul></div></div>'))

    # ---- Slide 9 · cash --------------------------------------------------- #
    s9 = _slide(9, "Cash Management", "USD Money Market: SGOV", (
        '<div class="two">'
        '<div class="stat"><h3>SGOV · iShares 0–3 Month Treasury Bond ETF</h3>'
        '<span class="k" style="color:#b0872a;font-weight:700;display:block;margin-top:14px">'
        'Expense ratio</span><div style="font-size:13.5px">0.09% (among the lowest in class)</div>'
        '<span class="k" style="color:#b0872a;font-weight:700;display:block;margin-top:12px">'
        '30-day SEC yield</span><div style="font-size:13.5px">≈3.55% (trailing 12-month '
        'distribution ≈3.85%)</div>'
        '<span class="k" style="color:#b0872a;font-weight:700;display:block;margin-top:12px">'
        'Holdings</span><div style="font-size:13.5px">0–3 month US T-bills; near-zero rate and '
        'credit risk</div>'
        '<span class="k" style="color:#b0872a;font-weight:700;display:block;margin-top:12px">'
        'Scale / liquidity</span><div style="font-size:13.5px">≈$96bn AUM, monthly distributions, '
        'excellent liquidity</div></div>'
        '<div><h3>Dual role in the portfolio</h3>'
        '<div class="stat" style="margin-bottom:14px"><b style="color:#1e2a56">1 · Benchmark '
        'allocation, 10%</b><p style="margin-top:6px">A permanent $300k liquidity reserve, '
        'available at any time</p></div>'
        '<div class="navycard"><b style="color:#c8a24a">2 · Tactical "reservoir"</b>'
        '<p style="margin-top:6px;font-size:13px;color:#cdd5ee;line-height:1.5">Currently '
        'warehouses ~$2.2m of capital awaiting deployment (equities 40% + gold 20% + later bond '
        'tranches) — earning ~3.5–3.9% annualised while waiting for entry points; yields rise '
        'further if the Fed hikes</p></div></div></div>'))

    # ---- Slide 10 · current-stage plan ------------------------------------ #
    plan = [("SPY · S&P 500", "30%", "5%", "150,000", "Starter position; add on pullbacks per triggers"),
            ("QQQ · Nasdaq-100", "20%", "5%", "150,000", "Starter position; add on pullbacks per triggers"),
            ("Bonds (BND+VCIT)", "20%", "6.7%", "200,000", "Tranche 1 of 3; later tranches straddle FOMC meetings"),
            ("Gold · GLDM", "20%", "0%", "0", "Gold at $4,067 is still above $4,000; buy in stages once triggered"),
            ("Money market · SGOV", "10%", "83.3%", "2,500,000", "$300k benchmark + $2.2m deployment reservoir")]
    pr = "".join(f'<tr><td>{n}</td><td class="mono">{lt}</td>'
                 f'<td class="mono"><b>{now}</b></td><td class="mono">{amt}</td>'
                 f'<td style="font-size:12.5px;color:#5a648a">{note}</td></tr>'
                 for n, lt, now, amt, note in plan)
    s10 = _slide(10, "Phase 1", "Current-Stage Allocation (Execute Now)", (
        f'<table class="tbl"><tr><th>Asset / vehicle</th><th>LT target</th><th>Now</th>'
        f'<th>Amount (USD)</th><th>Notes</th></tr>{pr}</table>'
        '<p class="note">"Now" weights are the recommended phased-entry plan (derived from the '
        'client\'s strategy), not the long-term benchmark; the money-market reservoir is drawn '
        'down as triggers fire.</p>'))

    # ---- Slide 11 · triggers ---------------------------------------------- #
    trig = [("S&P 500 / SPY", "Index ≈7,440", "-15% → ≈6,325<br>Add to 2/3 of target (≈20% cum.)",
             "-20% → ≈5,950<br>Complete to 30%"),
            ("Nasdaq-100 / QQQ", "High ≈30,660", "-15% → ≈26,060<br>Add to 2/3 of target (≈13% cum.)",
             "-20% → ≈24,530<br>Complete to 20%"),
            ("Gold / GLDM", "Spot $4,067", "Below $4,000<br>Buy 10% ($300k)",
             "Below $3,850<br>Complete to 20% ($600k)"),
            ("Bonds / BND+VCIT", "Tranche-based (not price-triggered)",
             "Tranche 2, $200k:<br>after Sep–Oct FOMC",
             "Tranche 3, $200k: after Dec FOMC,<br>or earlier if 10-yr yield ≥ 5%")]
    tr = "".join(f'<tr><td>{a}</td><td class="metric">{ref}</td><td>{t1}</td><td>{t2}</td></tr>'
                 for a, ref, t1, t2 in trig)
    s11 = _slide(11, "Execution Triggers", "Phased-Entry Trigger Conditions", (
        f'<table class="tbl"><tr><th>Asset</th><th>Reference high / condition</th>'
        f'<th>Trigger 1 (add)</th><th>Trigger 2 (complete)</th></tr>{tr}</table>'
        '<p class="note"><b>Discipline:</b> Execute mechanically when triggers hit — no '
        'second-guessing. If nothing triggers within 12 months, re-assess the benchmark against '
        'valuations and the rate environment rather than leaving capital idle indefinitely.</p>'))

    # ---- Slide 12 · roadmap ----------------------------------------------- #
    steps = [("1", "Now — July 2026", "Account setup & initial buys",
              "Buy SPY 5% + QQQ 5% + bond tranche 1 ($200k); park remaining $2.5m in SGOV; "
              "set price alerts on gold and both indices", True),
             ("2", "Q3 — Jul–Sep", "Monitor & execute triggers",
              "Watch the Sep FOMC; start the gold programme if spot breaks $4,000; add equities "
              "per the trigger table on any pullback", False),
             ("3", "Q4 — Oct–Dec", "Complete bond tranches",
              "Execute bond tranche 2 after the Oct FOMC and tranche 3 after the Dec FOMC; "
              "year-end progress review", False),
             ("4", "From 2027", "Rebalancing regime",
              "Review every six months; rebalance back to benchmark whenever any asset drifts "
              "±5% from target", False)]
    sc = "".join(f'<div class="step {"solid" if solid else ""}"><div class="n">{n}</div>'
                 f'<div class="when">{when}</div><div class="st-t">{title}</div>'
                 f'<p>{body}</p></div>' for n, when, title, body, solid in steps)
    s12 = _slide(12, "Roadmap", "Implementation Roadmap", f'<div class="road">{sc}</div>')

    slides = [s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12]
    return STYLE + '<div class="wrap">' + "".join(slides) + "</div>"
