"""build_ui.py — family-office copilot UI with an intake/onboarding flow.

Two stages in one artifact:
  1. Intake — the staffer adds the client's tuned statements (digested client-side
     by a JS port of statement_parser), sets the mandate + risk appetite, and can
     vary target allocation, bands, liquidity floor, FX cap, position cap and
     exclusions. "Generate" digests + builds the consolidated book.
  2. Copilot — Overview digest, Ask-the-book, Holdings, Suitability, Data quality,
     and an Output view — all recomputed LIVE as the staffer changes parameters.

Everything is real: documents are parsed in the browser, suitability is recomputed
from the parameters, every number carries provenance. No backend (works in the
artifact sandbox). Raw statement text is embedded so the samples load offline; the
drop zone also parses real uploads of the same formats.

Run:  python3 build_ui.py  ->  copilot_ui.html
"""
from __future__ import annotations

import json
from pathlib import Path

SD = Path(__file__).parent / "synthetic_statements"
RAW = {
    "A": SD.joinpath("custodianA_uob.csv").read_text(),
    "B": SD.joinpath("custodianB_eurobank.csv").read_text(),
    "C": SD.joinpath("custodianC_familyoffice.json").read_text(),
}

PAGE = r"""
<style>
:root{
  --bg:#e9edf4; --panel:#ffffff; --rail:#0f1b3d; --rail-ink:#c7d0ea; --rail-active:#1b2c5c;
  --ink:#15223f; --ink-soft:#5a648a; --line:#dbe1ee; --gold:#9c7a24; --field:#f3f6fb;
  --ok:#2f7a52; --ok-bg:#e4f1e9; --warn:#9a6410; --warn-bg:#f7ebd2; --crit:#a8442f; --crit-bg:#f6ddd6;
  --mono-ink:#6b7599;
  --serif:"Hoefler Text","Iowan Old Style","Palatino Linotype",Georgia,serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:"SF Mono",ui-monospace,"JetBrains Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#080f24; --panel:#111d42; --rail:#0a1330; --rail-ink:#9fb0d8; --rail-active:#1a2a55;
  --ink:#eaeefa; --ink-soft:#93a0c4; --line:#25335c; --gold:#d2ac57; --field:#0c1530;
  --ok:#5cc08a; --ok-bg:#173026; --warn:#e8b866; --warn-bg:#33290f; --crit:#e0876a; --crit-bg:#331d16; --mono-ink:#8592b8;
}}
:root[data-theme="light"]{--bg:#e9edf4;--panel:#ffffff;--rail:#0f1b3d;--rail-ink:#c7d0ea;--rail-active:#1b2c5c;
  --ink:#15223f;--ink-soft:#5a648a;--line:#dbe1ee;--gold:#9c7a24;--field:#f3f6fb;
  --ok:#2f7a52;--ok-bg:#e4f1e9;--warn:#9a6410;--warn-bg:#f7ebd2;--crit:#a8442f;--crit-bg:#f6ddd6;--mono-ink:#6b7599;}
:root[data-theme="dark"]{--bg:#080f24;--panel:#111d42;--rail:#0a1330;--rail-ink:#9fb0d8;--rail-active:#1a2a55;
  --ink:#eaeefa;--ink-soft:#93a0c4;--line:#25335c;--gold:#d2ac57;--field:#0c1530;
  --ok:#5cc08a;--ok-bg:#173026;--warn:#e8b866;--warn-bg:#33290f;--crit:#e0876a;--crit-bg:#331d16;--mono-ink:#8592b8;}
:root{color-scheme:light}
@media (prefers-color-scheme:dark){:root{color-scheme:dark}}
:root[data-theme="light"]{color-scheme:light}
:root[data-theme="dark"]{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);-webkit-font-smoothing:antialiased}
.app{display:grid;grid-template-columns:230px 1fr;min-height:100vh}
.rail{background:var(--rail);color:var(--rail-ink);padding:22px 14px;display:flex;flex-direction:column;gap:4px}
.brand{color:#fff;font-family:var(--serif);font-size:18px;font-weight:600;line-height:1.15;margin:2px 8px 8px}
.brand b{color:var(--gold);display:block;font-family:var(--mono);font-size:9.5px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;margin-top:5px}
.nav{background:none;border:none;color:var(--rail-ink);font:inherit;font-size:13.5px;text-align:left;padding:9px 12px;border-radius:7px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:8px}
.nav:hover{background:var(--rail-active)}.nav.on{background:var(--rail-active);color:#fff;font-weight:600}
.nav:disabled{opacity:.4;cursor:not-allowed}
.nav .dot{font-family:var(--mono);font-size:10px;font-weight:700;padding:1px 7px;border-radius:20px;background:var(--rail-active);color:#fff}
.dot.crit{background:#8f3623;color:#fff}.dot.warn{background:#7a4d0c;color:#fff}
.rail .foot{font-family:var(--mono);font-size:9.5px;color:var(--rail-ink);opacity:.6;padding:4px 8px;line-height:1.5}
.railfoot{margin-top:auto;display:flex;flex-direction:column;gap:5px;padding-top:12px;border-top:1px solid var(--rail-active);margin-top:auto}
.railgen{font:inherit;font-weight:600;font-size:13.5px;padding:11px 12px;border:none;border-radius:8px;background:var(--gold);color:#1a1206;cursor:pointer;margin:6px 0}
.railgen:enabled:hover{filter:brightness(1.06)}
.railgen:disabled{opacity:.4;cursor:not-allowed}
.main{padding:26px 30px 60px;max-width:1060px}
.view{display:none}.view.on{display:block}
h1{font-family:var(--serif);font-size:26px;font-weight:600;margin:0 0 3px;letter-spacing:-.01em}
h2{font-family:var(--serif);font-size:18px;font-weight:600;margin:0 0 10px}
.sub{color:var(--ink-soft);font-size:13px;margin:0 0 18px}
.eyebrow{font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--gold);margin:22px 0 10px;font-weight:700}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:820px){.grid2{grid-template-columns:1fr}}
/* intake */
.drop{border:1.5px dashed var(--line);border-radius:9px;padding:16px;text-align:center;color:var(--ink-soft);font-size:13px}
.drop.hot{border-color:var(--gold);background:var(--field)}
.docrow{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--line);font-size:13px}
.docrow:last-child{border:none}
.docrow .x{margin-left:auto;color:var(--crit);cursor:pointer;font-family:var(--mono)}
.samples{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}
.samp{font-size:12px;padding:6px 11px;border:1px solid var(--line);border-radius:20px;background:none;color:var(--ink-soft);cursor:pointer}
.samp:hover{border-color:var(--gold);color:var(--ink)}
.field{display:flex;flex-direction:column;gap:5px;margin-bottom:12px}
.field label{font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.04em}
select,input[type=number],input[type=text]{font:inherit;font-size:13.5px;padding:8px 10px;border:1px solid var(--line);border-radius:7px;background:var(--field);color:var(--ink)}
select:focus,input:focus{outline:none;border-color:var(--gold)}
input[type=range]{accent-color:var(--gold)}
.rangewrap{display:flex;align-items:center;gap:10px}.rangewrap output{font-family:var(--mono);font-size:12px;min-width:44px;text-align:right}
.allocrow{display:grid;grid-template-columns:90px 1fr 118px;align-items:center;gap:10px;margin:7px 0}
.allocrow input[type=range]{width:100%}
.numwrap{display:flex;align-items:center;gap:5px;justify-content:flex-end}
.numin{font:inherit;font-size:12.5px;width:88px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--field);color:var(--ink);text-align:right;font-variant-numeric:tabular-nums}
.numin:focus{outline:none;border-color:var(--gold)}
.numin::-webkit-inner-spin-button,.numin::-webkit-outer-spin-button{opacity:1;margin-left:9px}
.pcts{font-family:var(--mono);font-size:12px;color:var(--ink-soft)}
.ynrow{display:flex;gap:22px;flex-wrap:wrap;margin-top:2px}
.yn{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.yn-opt{cursor:pointer;display:flex}
.yn-opt input{position:absolute;opacity:0;width:0;height:0}
.yn-opt span{padding:6px 16px;font-size:13px;background:var(--field);color:var(--ink-soft);user-select:none}
.yn-opt:first-child span{border-right:1px solid var(--line)}
.yn-opt input:checked+span{background:var(--gold);color:#1a1206;font-weight:600}
.yn-opt input:focus-visible+span{outline:2px solid var(--gold);outline-offset:-2px}
.exrow{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:9px 0;font-size:13px}
.sumbad{font-family:var(--mono);font-size:12px;padding:3px 9px;border-radius:6px;display:inline-block;margin-top:6px}
.sumbad.ok{background:var(--ok-bg);color:var(--ok)}.sumbad.bad{background:var(--crit-bg);color:var(--crit)}
.toggles{display:flex;flex-wrap:wrap;gap:8px}
.tgl{font-size:12px;padding:6px 10px;border:1px solid var(--line);border-radius:7px;cursor:pointer;background:var(--field);user-select:none}
.tgl.on{border-color:var(--gold);color:var(--gold);font-weight:600}
.genbtn{font:inherit;font-weight:600;font-size:15px;padding:13px 26px;border:none;border-radius:9px;background:var(--rail);color:#fff;cursor:pointer;margin-top:6px}
.genbtn:disabled{opacity:.45;cursor:not-allowed}
.hint{font-size:12px;color:var(--ink-soft);margin-top:6px}
/* kpis / bars / attn / ask / tables reused */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px}
.k-lab{font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.05em}
.k-val{font-family:var(--serif);font-size:25px;font-weight:600;font-variant-numeric:tabular-nums;margin-top:5px;line-height:1}
.k-src{font-family:var(--mono);font-size:9.5px;color:var(--mono-ink);margin-top:7px;line-height:1.3}
.bars{display:flex;flex-direction:column;gap:9px}
.bar-row{display:grid;grid-template-columns:120px 1fr 118px;align-items:center;gap:12px;font-size:13px}
.bar-track{background:var(--line);border-radius:5px;height:10px;position:relative;overflow:hidden}
.bar-fill{height:100%;background:var(--gold);border-radius:5px}
.bar-tgt{position:absolute;top:-2px;height:14px;width:2px;background:var(--ink)}
.bar-val{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right;font-size:11.5px;color:var(--ink-soft)}
.att-row{display:flex;gap:11px;align-items:baseline;padding:10px 2px;border-bottom:1px solid var(--line)}
.att-row:last-child{border:none}
.pill{font-family:var(--mono);font-size:10px;font-weight:700;padding:2px 8px;border-radius:5px;white-space:nowrap;text-transform:uppercase;letter-spacing:.03em}
.pill.block{background:var(--crit-bg);color:var(--crit)}.pill.flag,.pill.review{background:var(--warn-bg);color:var(--warn)}
.pill.disclose,.pill.ok{background:var(--ok-bg);color:var(--ok)}
.att-d{font-size:13px}
.askwrap{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px}
.askbar{display:flex;gap:10px}
#q{flex:1;font:inherit;font-size:15px;padding:12px 14px;border:1.5px solid var(--line);border-radius:9px;background:var(--field);color:var(--ink)}
.askbtn{font:inherit;font-weight:600;font-size:14px;padding:0 20px;border:none;border-radius:9px;background:var(--rail);color:#fff;cursor:pointer}
.chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}
.chip{font-size:12px;padding:6px 11px;border:1px solid var(--line);border-radius:20px;background:none;color:var(--ink-soft);cursor:pointer}
.chip:hover{border-color:var(--gold);color:var(--ink)}
.ans-sum{font-size:16px;line-height:1.5;font-family:var(--serif);margin-top:16px}
.fact{display:grid;grid-template-columns:190px 1fr;gap:12px;font-size:12.5px;padding:6px 0;border-top:1px solid var(--line);margin-top:8px}
.fact .fl{color:var(--ink-soft)}.fact .fv{font-variant-numeric:tabular-nums}
.fact .src{grid-column:1/-1;font-family:var(--mono);font-size:10px;color:var(--mono-ink)}
.disc{font-family:var(--mono);font-size:10.5px;color:var(--mono-ink);margin-top:14px;line-height:1.5}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--ink-soft);border-bottom:1px solid var(--line);padding:8px}
td{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.warnflag{color:var(--crit);font-family:var(--mono);font-size:11px}
.cust-h{font-family:var(--mono);font-size:11px;color:var(--gold);letter-spacing:.05em;margin:16px 0 4px;font-weight:700}
@media(max-width:760px){.app{grid-template-columns:1fr}.rail{flex-direction:row;flex-wrap:wrap}.rail .foot{display:none}.brand{width:100%}}
</style>

<div class="app">
  <nav class="rail">
    <div class="brand">Meridian<span style="font-family:var(--serif);font-weight:600"> Family Office</span><b>AI Copilot · Confidential</b></div>
    <button class="nav on" data-view="intake">New client intake</button>
    <button class="railgen" id="gen" onclick="generate()" disabled>Digest &amp; generate ▸</button>
    <button class="nav" data-view="overview" disabled>Overview</button>
    <button class="nav" data-view="ask" disabled>Ask the book</button>
    <button class="nav" data-view="holdings" disabled>Holdings <span id="nh" class="dot"></span></button>
    <button class="nav" data-view="suit" disabled>Suitability <span id="ns" class="dot"></span></button>
    <button class="nav" data-view="dq" disabled>Data quality <span id="nd" class="dot"></span></button>
    <button class="nav" data-view="output" disabled>Output</button>
    <div class="railfoot">
      <div class="foot" id="genhint">Add at least one document to continue.</div>
      <div class="foot" id="prov">No documents digested yet.</div>
    </div>
  </nav>
  <main class="main">
    <!-- INTAKE -->
    <section class="view on" id="v-intake">
      <h1>New client intake</h1>
      <p class="sub">Add the client's tuned statements, set the mandate and risk appetite, tune the parameters, then generate the consolidated view.</p>
      <div class="grid2">
        <div>
          <div class="eyebrow">1 · Client documents</div>
          <div class="card">
            <div class="drop" id="drop">Drop tuned statement files here (.csv / .json)<br><span class="hint">or load a sample custodian below</span></div>
            <div class="samples">
              <button class="samp" onclick="addSample('A')">+ UOB (USD, per-share)</button>
              <button class="samp" onclick="addSample('B')">+ Banque Privée (EUR/CHF, % nominal)</button>
              <button class="samp" onclick="addSample('C')">+ Alpine Trust (alts + Lombard)</button>
            </div>
            <div id="doclist" style="margin-top:12px"></div>
          </div>
          <div class="eyebrow">2 · Mandate &amp; risk</div>
          <div class="card">
            <div class="grid2" style="gap:0 16px">
              <div class="field"><label>Mandate</label><select id="mandate">
                <option value="execution_only">Execution-only</option>
                <option value="advisory" selected>Advisory</option>
                <option value="discretionary">Discretionary</option></select></div>
              <div class="field"><label>Risk appetite</label><select id="risk">
                <option value="conservative">Conservative</option>
                <option value="moderate">Moderate</option>
                <option value="balanced" selected>Balanced</option>
                <option value="growth">Growth</option>
                <option value="aggressive">Aggressive</option></select></div>
              <div class="field"><label>Objective</label><select id="objective">
                <option>preservation</option><option>income</option>
                <option selected>balanced</option><option>growth</option></select></div>
              <div class="field"><label>Time horizon (yrs)</label><input type="number" id="horizon" value="10" min="1" max="40"></div>
              <div class="field"><label>Base currency</label><select id="baseccy"><option selected>USD</option><option>EUR</option><option>CHF</option><option>SGD</option></select></div>
              <div class="field"><label>US person? (tax)</label><select id="usperson"><option value="no" selected>No</option><option value="yes">Yes</option></select></div>
            </div>
            <div class="ynrow">
              <div class="field" style="margin-bottom:0"><label>Complex products allowed?</label>
                <div class="yn">
                  <label class="yn-opt"><input type="radio" name="complex" value="yes" checked><span>Yes</span></label>
                  <label class="yn-opt"><input type="radio" name="complex" value="no"><span>No</span></label></div></div>
              <div class="field" style="margin-bottom:0"><label>Accredited investor?</label>
                <div class="yn">
                  <label class="yn-opt"><input type="radio" name="accredited" value="yes" checked><span>Yes</span></label>
                  <label class="yn-opt"><input type="radio" name="accredited" value="no"><span>No</span></label></div></div>
            </div>
          </div>
        </div>
        <div>
          <div class="eyebrow">3 · Target allocation &amp; limits</div>
          <div class="card">
            <div id="allocs"></div>
            <div id="allocsum" class="sumbad ok">Total 100%</div>
            <div class="field" style="margin-top:14px"><label>Band tolerance (± around target)</label>
              <div class="rangewrap"><input type="range" id="tol" min="5" max="30" step="0.1" value="15"><input type="number" class="numin" id="tol-o" min="5" max="30" step="0.1" value="15"><span class="pcts">%</span></div></div>
            <div class="field"><label>Minimum liquidity</label>
              <div class="rangewrap"><input type="range" id="minliq" min="0" max="50" step="0.1" value="10"><input type="number" class="numin" id="minliq-o" min="0" max="50" step="0.1" value="10"><span class="pcts">%</span></div></div>
            <div class="field"><label>Max unhedged FX</label>
              <div class="rangewrap"><input type="range" id="maxfx" min="0" max="60" step="0.1" value="30"><input type="number" class="numin" id="maxfx-o" min="0" max="60" step="0.1" value="30"><span class="pcts">%</span></div></div>
            <div class="field"><label>Max single position (funds)</label>
              <div class="rangewrap"><input type="range" id="maxpos" min="10" max="60" step="0.1" value="40"><input type="number" class="numin" id="maxpos-o" min="10" max="60" step="0.1" value="40"><span class="pcts">%</span></div></div>
            <div class="field"><label>Exclusions (won't hold)</label>
              <div class="exrow"><span>Exclude alternatives?</span>
                <div class="yn"><label class="yn-opt"><input type="radio" name="excl-alternatives" value="yes"><span>Yes</span></label><label class="yn-opt"><input type="radio" name="excl-alternatives" value="no" checked><span>No</span></label></div></div>
              <div class="exrow"><span>Exclude real estate?</span>
                <div class="yn"><label class="yn-opt"><input type="radio" name="excl-real_estate" value="yes"><span>Yes</span></label><label class="yn-opt"><input type="radio" name="excl-real_estate" value="no" checked><span>No</span></label></div></div>
              <div class="exrow"><span>Exclude commodities?</span>
                <div class="yn"><label class="yn-opt"><input type="radio" name="excl-commodity" value="yes"><span>Yes</span></label><label class="yn-opt"><input type="radio" name="excl-commodity" value="no" checked><span>No</span></label></div></div>
              </div>
          </div>
          <div class="hint">Set the documents and parameters, then press <b>Digest &amp; generate</b> in the left sidebar.</div>
        </div>
      </div>
    </section>

    <!-- OVERVIEW -->
    <section class="view" id="v-overview">
      <h1>Consolidated overview</h1><p class="sub" id="ov-sub"></p>
      <div class="kpis" id="kpis"></div>
      <div class="eyebrow">Allocation — actual vs target</div>
      <div class="card"><div class="bars" id="alloc"></div><div class="hint" style="margin-top:10px">Bar = actual · marker = target. Tune parameters on the <b>Output</b> tab to see suitability update live.</div></div>
      <div class="eyebrow">Needs attention</div>
      <div class="card"><div id="attn"></div></div>
    </section>

    <!-- ASK -->
    <section class="view" id="v-ask">
      <h1>Ask the book</h1><p class="sub">Answers are computed from the digested statements — every figure shows its source.</p>
      <div class="askwrap">
        <div class="askbar"><input id="q" placeholder="e.g. How much is unhedged? What's my largest position?">
          <button class="askbtn" onclick="ask(document.getElementById('q').value)">Ask</button></div>
        <div class="chips" id="chips"></div><div id="ans"></div>
        <div class="disc">Numbers come from the deterministic engine over the digested book; the assistant never invents a figure. In production the same computed answer is phrased by a grounded LLM.</div>
      </div>
    </section>

    <section class="view" id="v-holdings"><h1>Holdings by custodian</h1><p class="sub" id="hold-sub"></p><div id="holdings"></div></section>
    <section class="view" id="v-suit"><h1>Suitability</h1><p class="sub">Checked against the mandate bands — recomputes when you change parameters.</p><div class="card"><div id="suit"></div></div></section>
    <section class="view" id="v-dq"><h1>Data quality</h1><p class="sub">Surfaced, not silently corrected — resolve before the book is treated as clean.</p><div class="card"><div id="dq"></div></div></section>

    <!-- OUTPUT (live params) -->
    <section class="view" id="v-output">
      <h1>Output &amp; parameters</h1><p class="sub">Vary the mandate, risk and limits — the whole view recomputes live.</p>
      <div class="grid2">
        <div class="card">
          <h2>Live parameters</h2>
          <div class="field"><label>Mandate</label><select id="o-mandate" onchange="syncFromOutput()">
            <option value="execution_only">Execution-only</option><option value="advisory">Advisory</option><option value="discretionary">Discretionary</option></select></div>
          <div class="field"><label>Risk appetite</label><select id="o-risk" onchange="applyPreset(this.value);syncFromOutput()">
            <option value="conservative">Conservative</option><option value="moderate">Moderate</option><option value="balanced">Balanced</option><option value="growth">Growth</option><option value="aggressive">Aggressive</option></select></div>
          <div id="o-allocs"></div><div id="o-allocsum" class="sumbad ok">Total 100%</div>
          <div class="field" style="margin-top:12px"><label>Min liquidity</label><div class="rangewrap"><input type="range" id="o-minliq" min="0" max="50" step="0.1" oninput="syncFromOutput()"><input type="number" class="numin" id="o-minliq-o" min="0" max="50" step="0.1" oninput="document.getElementById('o-minliq').value=this.value;syncFromOutput()"><span class="pcts">%</span></div></div>
          <div class="field"><label>Max unhedged FX</label><div class="rangewrap"><input type="range" id="o-maxfx" min="0" max="60" step="0.1" oninput="syncFromOutput()"><input type="number" class="numin" id="o-maxfx-o" min="0" max="60" step="0.1" oninput="document.getElementById('o-maxfx').value=this.value;syncFromOutput()"><span class="pcts">%</span></div></div>
        </div>
        <div class="card"><h2>Result</h2><div id="outsummary"></div></div>
      </div>
      <div class="eyebrow">Rebalancing proposal — before → after</div>
      <div class="card scroll"><div id="proposal"></div></div>
    </section>
  </main>
</div>

<script>
const RAW = __RAW__;
const TODAY = new Date("2026-07-04");
const FX = {USD:1, EUR:1.08, CHF:1.11, SGD:0.74};
const HOUSE = {"HC-USTREAS5Y":{it:"govt_bond",issuer:"US Treasury"}};
const ILLIQ = new Set(["alternatives","real_estate"]);
const PRESETS = {
  conservative:{equity:.20,fixed_income:.45,commodity:.05,cash:.30},
  moderate:{equity:.35,fixed_income:.40,commodity:.05,cash:.20},
  balanced:{equity:.50,fixed_income:.30,commodity:.10,cash:.10},
  growth:{equity:.65,fixed_income:.20,commodity:.05,cash:.10},
  aggressive:{equity:.80,fixed_income:.10,commodity:.05,cash:.05}};
const CLASSES = ["equity","fixed_income","commodity","cash"];
const CLASS_SYN = {equity:["equity","equities","stock","shares"],fixed_income:["fixed income","bond","bonds","credit"],
  commodity:["commodity","gold","commodities"],cash:["cash","money market"],
  alternatives:["alternative","private equity","pe fund"],real_estate:["real estate","property","real-estate"]};

let DOCS = {};            // key -> raw text
let BOOK = null;          // digested
let PROFILE = {mandate:"advisory",risk:"balanced",target:{...PRESETS.balanced},tol:.15,
  minLiquid:.10,maxFx:.30,maxPos:.40,exclude:new Set(),complexOk:true};

const usd=x=>"$"+Math.round(x).toLocaleString("en-US");
const pct=x=>(x*100).toFixed(1)+"%";

/* ---------- document digestion (JS port of statement_parser) ---------- */
function meta(text){const m={};text.split("\n").filter(l=>l.startsWith("#")).forEach(l=>
  l.replace(/^#/,"").split("|").forEach(t=>{const i=t.indexOf("=");if(i>0)m[t.slice(0,i).trim()]=t.slice(i+1).trim();}));return m;}
function parseCsv(text,sep,comma){const m=meta(text);
  const rows=text.split("\n").filter(l=>l&&!l.startsWith("#"));
  const H=rows.shift().split(sep);const num=s=>parseFloat(comma?s.replace(",","."):s);
  const pos=[];rows.forEach(r=>{const c=r.split(sep);const o={};H.forEach((h,i)=>o[h.trim()]=(c[i]||"").trim());
    const ident=o.identifier||o.code, idt=o.id_type||o.code_type, name=o.name||o.libelle,
      cls=o.asset_class||o.classe, qty=num(o.quantity||o.nominal_ou_qte), price=num(o.price||o.cours),
      ccy=o.price_ccy||o.devise, basis=o.valuation_basis||o.base_valo, raw=(o.type||o.categorie||"").toUpperCase();
    const flags=[]; let it, issuer=null, resolved=true, id2=ident, idt2=idt;
    if(idt==="HOUSE"){const h=HOUSE[ident]; if(h){it=h.it;issuer=h.issuer;} else {flags.push("unresolved house-code '"+ident+"' — needs instrument mapping");resolved=false;}}
    if(!it) it={ETF:"equity_etf",MMF:"money_market",CASH:"cash",OBLIGATION:cls==="fixed_income"?"govt_bond":"bond_etf",FONDS:"equity_etf",LIQUIDITE:"cash"}[raw]||"unknown";
    const mvc=basis==="pct_nominal"?qty*price/100:qty*price; const mv=mvc*(FX[ccy]||1);
    pos.push({name,asset_class:cls,instrument_type:it,custodian:m.custodian||"custodian",entity:m.entity||"ENT-A",
      currency:ccy,value:Math.round(mv*100)/100,flags,resolved,val_as_of:m.as_of||""});});
  return {custodian:m.custodian||"custodian",entity:m.entity||"ENT-A",stated:parseFloat(m.stated_total_usd||0),positions:pos,liabilities:[]};}
function parseJson(text){const d=JSON.parse(text);const pos=(d.positions||[]).map(p=>{const flags=[];
  if(p.valuation==="manual_nav"){const age=Math.round((TODAY-new Date(p.nav_as_of))/864e5);
    if(age>100)flags.push("stale manual valuation — NAV as of "+p.nav_as_of+" ("+age+"d old)");}
  return {name:p.name,asset_class:p.asset_class,instrument_type:p.instrument_type,custodian:d.custodian,
    entity:d.entity||"Holdco-2",currency:"USD",value:p.nav_usd,flags,resolved:true,val_as_of:p.nav_as_of||d.as_of};});
  return {custodian:d.custodian,entity:d.entity||"Holdco-2",stated:d.stated_total_usd||0,positions:pos,liabilities:d.liabilities||[]};}
function detect(text){try{JSON.parse(text);return "json";}catch(e){}
  return text.includes("categorie;")||text.includes(";code;")?"csvB":"csvA";}
function parseDoc(text){const t=detect(text);return t==="json"?parseJson(text):t==="csvB"?parseCsv(text,";",true):parseCsv(text,",",false);}

function digest(){const sts=Object.values(DOCS).map(parseDoc);
  const positions=[].concat(...sts.map(s=>s.positions));
  const liabilities=[].concat(...sts.map(s=>s.liabilities));
  const gross=positions.reduce((a,p)=>a+p.value,0);
  const debt=liabilities.reduce((a,l)=>a+Math.abs(l.balance),0);
  const recon=sts.map(s=>{const t=s.positions.reduce((a,p)=>a+p.value,0);const d=Math.round((t-s.stated)*100)/100;
    return {custodian:s.custodian,ok:Math.abs(d)<=Math.max(250,0.0002*s.stated),delta:d};});
  BOOK={positions,liabilities,gross:Math.round(gross*100)/100,debt,net:Math.round((gross-debt)*100)/100,recon,
    as_of:sts[0]?sts[0].positions[0]?.val_as_of||"2026-07-02":"", prov:"parsed from "+sts.length+" custodian statement(s); non-USD via static demo FX table (wire to a live feed)"};}

/* ---------- suitability (JS port of suitability_check core) ---------- */
function bands(){const b={};CLASSES.forEach(c=>{const t=PROFILE.target[c]||0;
  b[c]={min:Math.max(0,t-PROFILE.tol),max:Math.min(1,t+PROFILE.tol)};});return b;}
function enforce(status){return status!=="breach"?"disclose":({execution_only:"disclose",advisory:"flag",discretionary:"block"})[PROFILE.mandate];}
function computeSuit(){const g=BOOK.gross,by={};BOOK.positions.forEach(p=>by[p.asset_class]=(by[p.asset_class]||0)+p.value);
  const B=bands(),F=[];
  CLASSES.forEach(c=>{const w=(by[c]||0)/g,bd=B[c];
    if(w<bd.min||w>bd.max)F.push({e:enforce("breach"),d:`${c.replace("_"," ")} ${pct(w)} ${w<bd.min?"below min":"above max"} [${pct(bd.min)}–${pct(bd.max)}]`});});
  Object.keys(by).forEach(c=>{if(!CLASSES.includes(c)){const w=by[c]/g;
    if(PROFILE.exclude.has(c))F.push({e:enforce("breach"),d:`${c.replace("_"," ")} ${pct(w)} held but is on the exclusion list`});
    else F.push({e:enforce("breach"),d:`${c.replace("_"," ")} ${pct(w)} held but has no allocation band defined`});}});
  BOOK.positions.forEach(p=>{if(PROFILE.exclude.has(p.asset_class))return;
    if(p.asset_class==="cash"||p.instrument_type==="money_market")return;
    const w=p.value/g,cap=["single_stock","govt_bond","corp_bond"].includes(p.instrument_type)?0.10:PROFILE.maxPos;
    if(w>cap)F.push({e:enforce("breach"),d:`${p.name} ${pct(w)} > ${pct(cap)} single-position cap`});});
  const un=BOOK.positions.filter(p=>p.currency!=="USD").reduce((a,p)=>a+p.value,0)/g;
  if(un>PROFILE.maxFx)F.push({e:enforce("breach"),d:`unhedged non-USD ${pct(un)} > ${pct(PROFILE.maxFx)} cap`});
  const liq=BOOK.positions.filter(p=>!ILLIQ.has(p.asset_class)).reduce((a,p)=>a+p.value,0)/g;
  if(liq<PROFILE.minLiquid)F.push({e:enforce("breach"),d:`liquid ${pct(liq)} < ${pct(PROFILE.minLiquid)} minimum`});
  const rank={block:3,flag:2,disclose:1};F.sort((a,b)=>rank[b.e]-rank[a.e]);return F;}

/* ---------- Q&A tools ---------- */
const sumBy=f=>BOOK.positions.reduce((a,p)=>a+f(p),0),G=()=>BOOK.gross;
function tTotals(){const l=BOOK.debt/BOOK.net;return{summary:`Net worth is ${usd(BOOK.net)} — ${usd(G())} of assets less ${usd(BOOK.debt)} of borrowing (leverage ${pct(l)}).`,
  facts:[["Gross assets",usd(G()),BOOK.prov],["Liabilities",usd(BOOK.debt),"Lombard loan, Alpine Trust statement"],["Net worth",usd(BOOK.net),"gross − liabilities"],["Leverage",pct(l),"debt ÷ net worth"]]};}
function tByClass(c){const v=sumBy(p=>p.asset_class===c?p.value:0),n=BOOK.positions.filter(p=>p.asset_class===c).map(p=>p.name),lab=c.replace("_"," ");
  if(!n.length)return{summary:`There is no ${lab} exposure in the book.`,facts:[]};
  return{summary:`${lab[0].toUpperCase()+lab.slice(1)} exposure is ${usd(v)} — ${pct(v/G())} of gross, across ${n.length} holding(s).`,
   facts:[[`${lab} value`,usd(v),BOOK.prov],["% of gross",pct(v/G()),"computed"],["Holdings",n.join(", "),"custodian statements"]]};}
function tByCcy(){const by={};BOOK.positions.forEach(p=>by[p.currency]=(by[p.currency]||0)+p.value);
  const un=Object.entries(by).filter(([c])=>c!=="USD").reduce((a,[,v])=>a+v,0);
  const parts=Object.entries(by).sort((a,b)=>b[1]-a[1]).map(([c,v])=>`${c} ${pct(v/G())}`).join(", ");
  return{summary:`By currency: ${parts}. Unhedged non-USD exposure is ${usd(un)} (${pct(un/G())}).`,facts:[["Currency mix",parts,BOOK.prov],["Unhedged non-USD",`${usd(un)} (${pct(un/G())})`,"FX via static demo table"]]};}
function tByCust(name){const by={};BOOK.positions.forEach(p=>{(by[p.custodian]=by[p.custodian]||[]).push(p)});let ks=Object.keys(by);
  if(name){const m=ks.filter(k=>k.toLowerCase().includes(name));if(m.length)ks=m;}
  return{summary:"Holdings by custodian: "+ks.map(k=>`${k} ${usd(by[k].reduce((a,p)=>a+p.value,0))}`).join("; ")+".",
   facts:ks.map(k=>[k,`${usd(by[k].reduce((a,p)=>a+p.value,0))} · ${by[k].length} holdings`,`${k} statement`])};}
function tSuit(){const b=computeSuit().filter(f=>f.e!=="disclose");if(!b.length)return{summary:"The book is within all defined suitability bands.",facts:[]};
  return{summary:`${b.length} suitability issue(s) need attention.`,facts:b.map(f=>[f.e,f.d,"suitability engine"])};}
function tConc(){const t=[...BOOK.positions].sort((a,b)=>b.value-a.value).slice(0,3);
  return{summary:`Largest position is ${t[0].name} at ${usd(t[0].value)} (${pct(t[0].value/G())} of gross).`,facts:t.map(p=>[p.name,`${usd(p.value)} (${pct(p.value/G())})`,`${p.custodian} statement`])};}
function tRate(){const fi=BOOK.positions.filter(p=>p.asset_class==="fixed_income"),t=fi.reduce((a,p)=>a+p.value,0);
  return{summary:`Fixed-income exposure is ${usd(t)} across ${fi.length} bond(s). A precise +100bp impact needs each bond's effective duration, which is not sourced for these instruments — the assistant will not estimate it.`,facts:fi.map(p=>[p.name,usd(p.value),"duration not sourced → [SOURCE REQUIRED]"])};}
function tLiq(){const l=sumBy(p=>ILLIQ.has(p.asset_class)?0:p.value),il=G()-l;
  return{summary:`Liquid holdings are ${usd(l)} (${pct(l/G())}); illiquid (alternatives + real estate) are ${usd(il)} (${pct(il/G())}).`,facts:[["Liquid",`${usd(l)} (${pct(l/G())})`,BOOK.prov],["Illiquid",`${usd(il)} (${pct(il/G())})`,"alternatives + real estate"]]};}
function tDQ(){const f=[];BOOK.recon.forEach(r=>{if(!r.ok)f.push(["reconciliation",`${r.custodian}: Δ $${r.delta.toLocaleString()}`,"parsed vs stated total"]);});
  BOOK.positions.forEach(p=>(p.flags||[]).forEach(x=>f.push(["data flag",`${p.name}: ${x}`,`${p.custodian} statement`])));
  if(!f.length)return{summary:"No data-quality issues detected.",facts:[]};
  return{summary:`${f.length} data-quality item(s) to resolve.`,facts:f};}
function route(q){const s=q.toLowerCase();
  for(const[c,syn]of Object.entries(CLASS_SYN))if(syn.some(w=>s.includes(w))&&["expos","how much","holding","have","allocation","weight"," in "].some(w=>s.includes(w)))return()=>tByClass(c);
  if(["currency","fx"," eur"," chf","unhedged","dollar"].some(w=>s.includes(w)))return tByCcy;
  if(["custodian","uob","banque","alpine","hold at"].some(w=>s.includes(w))){const n=["uob","banque","alpine"].find(x=>s.includes(x))||"";return()=>tByCust(n);}
  if(["suitab","breach","mandate","complian","band","unsuitab"].some(w=>s.includes(w)))return tSuit;
  if(["concentrat","largest","biggest","single"].some(w=>s.includes(w)))return tConc;
  if(["rate","duration","interest","100bp","hike"].some(w=>s.includes(w)))return tRate;
  if(["stale","unresolved","data qual","reconcil","clean","issue"].some(w=>s.includes(w)))return tDQ;
  if(["liquid","illiquid"].some(w=>s.includes(w)))return tLiq;
  if(["net worth","total","leverage","debt","borrow","worth"].some(w=>s.includes(w)))return tTotals;
  for(const[c,syn]of Object.entries(CLASS_SYN))if(syn.some(w=>s.includes(w)))return()=>tByClass(c);
  return tTotals;}
function ask(q){if(!q||!q.trim()||!BOOK)return;document.getElementById("q").value=q;const a=route(q)();
  document.getElementById("ans").innerHTML=`<div class="ans-sum">${a.summary}</div>`+a.facts.map(([l,v,s])=>`<div class="fact"><span class="fl">${l}</span><span class="fv">${v}</span><span class="src">${s}</span></div>`).join("");}

/* ---------- intake wiring ---------- */
function docName(k){return {A:"UOB Private Bank.csv",B:"Banque Privée.csv",C:"Alpine Trust.json"}[k]||k;}
function addSample(k){DOCS[k]=RAW[k];renderDocs();}
function renderDocs(){const el=document.getElementById("doclist");const ks=Object.keys(DOCS);
  el.innerHTML=ks.map(k=>`<div class="docrow">📄 ${docName(k)}<span class="x" onclick="delDoc('${k}')">remove</span></div>`).join("")||'<div class="hint">No documents added.</div>';
  const has=ks.length>0;document.getElementById("gen").disabled=!has;
  document.getElementById("genhint").textContent=has?`${ks.length} document(s) ready to digest.`:"Add at least one document to continue.";}
function delDoc(k){delete DOCS[k];renderDocs();}
function yn(name){const el=document.querySelector(`input[name="${name}"]:checked`);return el?el.value==="yes":false;}
function renderAllocInputs(container,onchange){const t=PROFILE.target;
  document.getElementById(container).innerHTML=CLASSES.map(c=>{const v=Math.round((t[c]||0)*1000)/10;
    return `<div class="allocrow"><span>${c.replace("_"," ")}</span>`+
      `<input type="range" min="0" max="100" step="0.1" value="${v}" data-c="${c}">`+
      `<span class="numwrap"><input type="number" class="numin" min="0" max="100" step="0.1" value="${v}" data-c="${c}"><span class="pcts">%</span></span></div>`;}).join("");
  document.querySelectorAll(`#${container} input`).forEach(inp=>inp.addEventListener("input",e=>{
    const c=e.target.dataset.c,v=Math.max(0,Math.min(100,+e.target.value||0));
    PROFILE.target[c]=v/100;
    document.querySelectorAll(`#${container} input[data-c="${c}"]`).forEach(o=>{if(o!==e.target)o.value=v;});
    onchange();}));}
function allocSum(id){const s=CLASSES.reduce((a,c)=>a+(PROFILE.target[c]||0),0);const el=document.getElementById(id);
  el.textContent=`Total ${(s*100).toFixed(1)}%`;el.className="sumbad "+(Math.abs(s-1)<.005?"ok":"bad");return Math.abs(s-1)<.005;}
function readIntake(){PROFILE.mandate=val("mandate");PROFILE.risk=val("risk");
  PROFILE.tol=(+val("tol"))/100;PROFILE.minLiquid=(+val("minliq"))/100;PROFILE.maxFx=(+val("maxfx"))/100;PROFILE.maxPos=(+val("maxpos"))/100;
  PROFILE.complexOk=yn("complex");
  PROFILE.exclude=new Set(["alternatives","real_estate","commodity"].filter(c=>yn("excl-"+c)));}
const val=id=>document.getElementById(id).value;
function applyPreset(r){PROFILE.target={...PRESETS[r]};renderAllocInputs("allocs",()=>{allocSum("allocsum");});
  renderAllocInputs("o-allocs",syncFromOutput);allocSum("allocsum");allocSum("o-allocsum");}

function generate(){readIntake();digest();
  document.querySelectorAll(".nav").forEach(b=>b.disabled=false);
  // mirror params into output controls
  document.getElementById("o-mandate").value=PROFILE.mandate;
  document.getElementById("o-risk").value=PROFILE.risk;
  setRange("o-minliq",PROFILE.minLiquid*100,"o-minliq-o","%");setRange("o-maxfx",PROFILE.maxFx*100,"o-maxfx-o","%");
  renderAllocInputs("o-allocs",syncFromOutput);allocSum("o-allocsum");
  renderAll();gotoView("overview");}
const r1=x=>Math.round((+x)*10)/10;
function setRange(id,v,oid,suf){document.getElementById(id).value=v;document.getElementById(oid).value=r1(v);}
function syncFromOutput(){PROFILE.mandate=val("o-mandate");
  PROFILE.minLiquid=(+val("o-minliq"))/100;PROFILE.maxFx=(+val("o-maxfx"))/100;
  document.getElementById("o-minliq-o").value=r1(val("o-minliq"));
  document.getElementById("o-maxfx-o").value=r1(val("o-maxfx"));
  allocSum("o-allocsum");renderAll();}

/* ---------- render everything from BOOK + PROFILE ---------- */
function pill(e){return e;}
function renderAll(){if(!BOOK)return;const g=BOOK.gross,lev=BOOK.debt/BOOK.net,
  liq=BOOK.positions.filter(p=>!ILLIQ.has(p.asset_class)).reduce((a,p)=>a+p.value,0);
  document.getElementById("prov").textContent=BOOK.prov;
  document.getElementById("ov-sub").textContent=`As of ${BOOK.as_of} · ${new Set(BOOK.positions.map(p=>p.entity)).size} entities · ${new Set(BOOK.positions.map(p=>p.custodian)).size} custodians`;
  document.getElementById("hold-sub").textContent=document.getElementById("ov-sub").textContent;
  document.getElementById("kpis").innerHTML=[["Net worth",usd(BOOK.net),"gross − liabilities"],["Gross assets",usd(g),"Σ parsed holdings"],
    ["Leverage",pct(lev),"Lombard ÷ net"],["Liquid",pct(liq/g),"ex-alternatives / RE"]].map(([l,v,s])=>
    `<div class="card"><div class="k-lab">${l}</div><div class="k-val">${v}</div><div class="k-src">${s}</div></div>`).join("");
  // allocation actual vs target
  const by={};BOOK.positions.forEach(p=>by[p.asset_class]=(by[p.asset_class]||0)+p.value);
  const cls=[...new Set([...CLASSES,...Object.keys(by)])];
  document.getElementById("alloc").innerHTML=cls.map(c=>{const w=(by[c]||0)/g,t=PROFILE.target[c]||0;
    return `<div class="bar-row"><span>${c.replace("_"," ")}</span><span class="bar-track"><span class="bar-fill" style="width:${Math.min(100,w*100)}%"></span>${t?`<span class="bar-tgt" style="left:${Math.min(100,t*100)}%"></span>`:""}</span><span class="bar-val">${pct(w)}${t?` · tgt ${pct(t)}`:" · no target"}</span></div>`;}).join("");
  // needs attention = suitability (non-disclose) + data quality
  const attn=[...computeSuit().filter(f=>f.e!=="disclose").map(f=>[f.e,f.d]),...tDQ().facts.map(f=>["review",f[1]])];
  document.getElementById("attn").innerHTML=attn.map(([k,d])=>`<div class="att-row"><span class="pill ${k}">${k}</span><span class="att-d">${d}</span></div>`).join("")||'<div class="att-d">Nothing needs attention.</div>';
  // badges
  const suitN=computeSuit().filter(f=>f.e!=="disclose").length,dqN=tDQ().facts.length;
  badge("ns",suitN,suitN?"crit":"");badge("nd",dqN,dqN?"crit":"");badge("nh",BOOK.positions.length,"");
  // holdings
  const cust={};BOOK.positions.forEach(p=>{(cust[p.custodian]=cust[p.custodian]||[]).push(p)});
  document.getElementById("holdings").innerHTML=Object.entries(cust).map(([c,ps])=>{const tot=ps.reduce((a,p)=>a+p.value,0);
    return `<div class="cust-h">${c} · ${ps[0].entity}</div><div class="card scroll"><table><thead><tr><th>Holding</th><th>Class</th><th>Ccy</th><th class="n">Value (USD)</th></tr></thead><tbody>`+
      ps.map(p=>`<tr><td>${p.name}${p.resolved?"":' <span class="warnflag">· unresolved id</span>'}${(p.flags||[]).map(f=>`<div class="warnflag">⚠ ${f}</div>`).join("")}</td><td>${p.asset_class}</td><td>${p.currency}</td><td class="n">${usd(p.value)}</td></tr>`).join("")+
      `<tr><td colspan="3"><b>Total</b></td><td class="n"><b>${usd(tot)}</b></td></tr></tbody></table></div>`;}).join("");
  // suitability + dq panels
  const S=computeSuit();document.getElementById("suit").innerHTML=S.length?S.map(f=>`<div class="att-row"><span class="pill ${f.e}">${f.e}</span><span class="att-d">${f.d}</span></div>`).join(""):'<div class="att-d">Within all bands.</div>';
  document.getElementById("dq").innerHTML=tDQ().facts.map(f=>`<div class="att-row"><span class="pill review">${f[0]}</span><span class="att-d">${f[1]}<div class="k-src">${f[2]}</div></span></div>`).join("")||'<div class="att-d">No issues.</div>';
  // output summary
  const drift=cls.map(c=>{const w=(by[c]||0)/g,t=PROFILE.target[c]||0;return {c,w,t,d:w-t};});
  document.getElementById("outsummary").innerHTML=
    `<div class="ans-sum" style="margin-top:0">Mandate <b>${PROFILE.mandate.replace("_"," ")}</b> · risk <b>${PROFILE.risk}</b> · gate <b>${S.length?S[0].e:"clear"}</b></div>`+
    `<div class="scroll" style="margin-top:12px"><table><thead><tr><th>Class</th><th class="n">Actual</th><th class="n">Target</th><th class="n">Drift</th></tr></thead><tbody>`+
    drift.map(x=>`<tr><td>${x.c.replace("_"," ")}</td><td class="n">${pct(x.w)}</td><td class="n">${x.t?pct(x.t):"—"}</td><td class="n" style="color:${Math.abs(x.d)>PROFILE.tol?'var(--crit)':'var(--ink-soft)'}">${x.d>=0?"+":""}${pct(x.d)}</td></tr>`).join("")+
    `</tbody></table></div><div class="disc">${S.length} suitability item(s). Change mandate/risk/limits above to recompute.</div>`;
  renderProposal();
  document.getElementById("chips").innerHTML=["How much is unhedged?","What's my largest position?","Which holdings breach my mandate?","How much of the book is illiquid?","What happens if rates rise 1%?","Any data-quality issues?"].map(q=>`<button class="chip" onclick="ask('${q.replace(/'/g,"\\'")}')">${q}</button>`).join("");}
function renderProposal(){const g=BOOK.gross,by={};BOOK.positions.forEach(p=>by[p.asset_class]=(by[p.asset_class]||0)+p.value);
  const classes=[...new Set([...CLASSES,...Object.keys(by)])];
  let rows="",buys=0,sells=0,anyTrade=false;
  classes.forEach(c=>{const before=by[c]||0,bw=before/g,unbanded=!CLASSES.includes(c),
    t=unbanded?0:(PROFILE.target[c]||0),tgt=t*g,delta=tgt-before,after=unbanded?0:t;
    if(delta>1)buys+=delta;else if(delta<-1)sells+=-delta;
    const dir=delta>1?"buy":delta<-1?"sell":"—";if(dir!=="—")anyTrade=true;
    let note="in band";
    if(dir!=="—"&&ILLIQ.has(c))note="⚠ illiquid — subject to lockup / liquidity event";
    else if(unbanded&&before>0)note="not in mandate target — divest or amend mandate to add a sleeve";
    else if(dir==="buy")note="top up to target";else if(dir==="sell")note="trim to target";
    const col=dir==="buy"?"var(--ok)":dir==="sell"?"var(--crit)":"var(--ink-soft)";
    rows+=`<tr><td>${c.replace("_"," ")}</td><td class="n">${pct(bw)}</td><td class="n">${pct(t)}</td>`+
      `<td class="n" style="color:${col}">${dir==="—"?"—":(delta>0?"+":"−")+usd(Math.abs(delta))}</td>`+
      `<td class="n">${pct(after)}</td><td class="k-src" style="font-family:var(--mono)">${note}</td></tr>`;});
  const net=Math.round(buys-sells);
  const fixed=computeSuit().filter(f=>f.e!=="disclose"&&/(below min|above max|cap|no allocation|exclusion list)/.test(f.d)).length;
  const el=document.getElementById("proposal");
  if(!anyTrade){el.innerHTML='<div class="att-d">Book is within target — no rebalancing trades required.</div>';return;}
  el.innerHTML=`<table><thead><tr><th>Class</th><th class="n">Before</th><th class="n">Target</th><th class="n">Trade</th><th class="n">After</th><th>Note</th></tr></thead><tbody>${rows}`+
    `<tr><td colspan="3"><b>Self-funding check</b></td><td class="n" style="color:${Math.abs(net)<1000?"var(--ok)":"var(--crit)"}"><b>net ${net>=0?"+":"−"}${usd(Math.abs(net))}</b></td><td colspan="2" class="k-src" style="font-family:var(--mono)">buys ${usd(buys)} · sells ${usd(sells)}</td></tr></tbody></table>`+
    `<div class="disc">Rebalancing the four target classes to policy weight clears the ${fixed} allocation-band / single-position breach(es). Trades net to ≈$0 (self-funding); leverage of ${pct(BOOK.debt/BOOK.net)} is unchanged. <b>Illiquid sleeves (alternatives, real estate) cannot be traded on demand</b> — either amend the mandate to add those sleeves to the target, or stage the reduction against redemption windows. FX and liquidity checks depend on the specific instruments purchased and are not assumed resolved.</div>`;}
function badge(id,n,cls){const e=document.getElementById(id);if(!n){e.textContent="";e.className="dot";return;}e.textContent=n;e.className="dot "+cls;}

/* ---------- nav + init ---------- */
function gotoView(v){document.querySelectorAll(".nav").forEach(x=>x.classList.toggle("on",x.dataset.view===v));
  document.querySelectorAll(".view").forEach(x=>x.classList.remove("on"));document.getElementById("v-"+v).classList.add("on");
  if(v==="ask")document.getElementById("q").focus();}
document.addEventListener("DOMContentLoaded",()=>{
  renderDocs();applyPreset("balanced");
  ["tol","minliq","maxfx","maxpos"].forEach(id=>{const r=document.getElementById(id),o=document.getElementById(id+"-o");
    r.addEventListener("input",()=>{o.value=r.value;});
    o.addEventListener("input",()=>{r.value=o.value;});});
  document.getElementById("risk").addEventListener("change",e=>applyPreset(e.target.value));
  document.querySelectorAll(".nav").forEach(b=>b.addEventListener("click",()=>{if(!b.disabled)gotoView(b.dataset.view);}));
  document.getElementById("q").addEventListener("keydown",e=>{if(e.key==="Enter")ask(e.target.value);});
  // drop zone
  const dz=document.getElementById("drop");
  ["dragover","dragenter"].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.add("hot");}));
  ["dragleave","drop"].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.remove("hot");}));
  dz.addEventListener("drop",e=>{[...e.dataTransfer.files].forEach(f=>{const r=new FileReader();
    r.onload=()=>{DOCS[f.name]=r.result;renderDocs();};r.readAsText(f);});});
});
</script>
"""

html = PAGE.replace("__RAW__", json.dumps(RAW))
Path("copilot_ui.html").write_text(html)
print(f"wrote copilot_ui.html · {len(html):,} bytes · {len(RAW)} sample statements embedded")
