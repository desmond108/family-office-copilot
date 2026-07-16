"""app.py — the Family Office Copilot (Version 10), driven by the REAL engines.

Version 10 changes, over v9 (snapshot preserved as app_v9.py): the copilot no
longer SORTS the client's tactical instructions into typed items to review and
update the allocation with. Instead it passes them straight through. Tactical
instructions are now a plain free-text box; their verbatim text — together with
the intake parameters, the parsed client holdings + raw statement source, and the
research / other documents in full — is assembled into ONE self-contained prompt
(narrative.build_prompt) and handed to the AI, which analyses that material and
writes the proposal. The engine still computes every NUMBER deterministically
(FACTS: allocation, rebalance, suitability); the LLM narrates around it, so the
never-invent-a-number discipline holds. The prompt is surfaced on the Proposal
page — visible, editable and copyable — so the client can read it and test it with
alternative LLMs (a live Claude API drives the in-app "Generate" button when
DEMO_MODE=0). This drops v6–v8's classify → review → confirm tactical pipeline and
the v7 propose-allocation panel and v8 enforced price-trigger gating.

Version 7 adds, over v6 (snapshot preserved as app_v6.py): propose-allocations-
from-instructions. When the client's tactical instructions state target weights
("USD money market fund: 10%", "Gold ETF: 20%", "S&P 500 ETF: 30%"), the
classifier captures them as `allocation_target` items (asset_class + weight_pct);
the Intake page then shows a "Proposed allocation" panel that aggregates them per
sleeve (Nasdaq 20% + S&P 30% → equity 50%) and offers an "Apply to allocation
targets" button. Applying is an explicit analyst action (an on_click callback that
writes the sleeve inputs BEFORE they are re-instantiated), never silent — the
analyst still verifies and can adjust before analysing. Keeps the discipline: the
model only reads the client's stated percentages, and nothing drives the engine
until the human approves it.

Version 6 adds, over v5 (snapshot preserved as app_v5.py): tactical instructions.
Ad-hoc client guidance in plain language ("buy in tranches", "add Nasdaq only
after a 15-20% pullback", "gold below USD 4,000/oz", "low fees and good
liquidity") is varied but not unstructured — it clusters into four types (entry
trigger / execution style / selection criteria / question). The Intake page gains
a free-text box whose text a classifier (tactical_extract.py — an LLM pass, or a
keyword fallback for the keyless build) SORTS into typed items; the analyst
reviews / edits / confirms them (same extract -> review -> confirm gate as the v5
statement flow); confirmed entry triggers become a monitoring watchlist and every
item folds into the proposal as analyst guidance. The classifier only sorts and
copies the client's own words / levels — it never invents a threshold — so the
never-invent-a-number discipline holds. See tactical_instructions_design.md.

Version 5 adds, over v4 (snapshot preserved as app_v4.py): PDF / image client
statements. The client-documents uploader now accepts pdf/png/jpg; a vision model
(vision_extract.py) TRANSCRIBES the printed holdings into a canonical schema, the
analyst reviews/corrects them in an editable table, and only then does the
deterministic engine (parse_extracted + reconcile) do the math (FX, house-code
resolution, reconciliation). The model computes nothing — it only reads printed
figures — so the never-invent-a-number discipline holds, and the reconciliation
checksum catches a misread. Extraction needs an API key, so keyless/DEMO builds
guide the user to the CSV/JSON path instead.

Version 4 adds, over v3 (snapshot preserved as app_v3.py): a separate "Research
documents" sidebar uploader (formal research, distinct from the informal "Other
documents"); and a portable deck prompt on the Proposal page — the editable
"Prompt sent to LLM" is now self-contained (it inlines the full deck spec + FACTS
+ analyst guidance) with a copy button, so pasting it verbatim into any LLM chat
regenerates the whole proposal as a PPTX and a PDF.

Version 3 adds, over v2 (snapshot preserved as app_v3.py; see narrative_layer_v3.md):
a grounded LLM CIO commentary on the Proposal deck (narrative.py) — the one place an
LLM writes prose. The prompt hands Claude a FACTS block (the computed figures) plus an
ANALYST GUIDANCE block (sleeve notes + considerations, intent only), is surfaced on the
Proposal page in an EDITABLE text area, and degrades to a deterministic grounded summary
with no API key / in DEMO_MODE. It renders as an optional slide after the cover.

Version 2 added, over v1 (preserved as app_v1.py): a sidebar uploader for other documents (emails,
notes, research); FX + structured-products overlay sleeves in Allocation & limits;
a free-text note per sleeve; an "Ability to take risk" (capacity) input alongside
risk appetite; and a Proposal page that renders the house-format deck inline
(generate_proposal.py) with PPTX / PDF download buttons.

Unlike the browser artifact (which needed a JavaScript re-implementation of the
parser and suitability rules), this runs the actual Python modules server-side:

    statement_parser.py   -> parse tuned statements (real CSV/JSON adapters, FX, recon)
    suitability_check.py  -> the 8-rule guardrail engine, live on every parameter change
    portfolio_qa.py       -> deterministic Q&A tools (+ optional grounded Claude)
    datafeed.py           -> provenance-first live prices / fees / durations

Layout mirrors the artifact: a light left rail (brand + live book status) and a
spacious tabbed workspace whose first tab is a three-column intake page. No number
is invented; every figure carries provenance.

Run:  streamlit run app.py
      (first time:  pip install -r requirements.txt)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from statement_parser import (FX_SOURCE, STMT_DIR, TODAY, parse_csv_generic,
                              parse_custodian_c, parse_extracted, reconcile, to_holdings)
from suitability_check import (Bands, ConcentrationLimits, Constraints,
                               RiskProfile, suitability_check, worst_enforcement)
from portfolio_qa import Book, ask, ask_ai
from datafeed import resolve_key
import generate_proposal
import narrative
import vision_extract
import doc_extract
import macro_overlay


def copy_button(text: str, label: str = "📋 Copy to clipboard",
                key: str = "copy", height: int = 46):
    """An explicit, always-visible copy button (a small HTML/JS component).

    Streamlit's built-in copy affordance (the hover icon on st.code) is easy to
    miss, so this renders a real button. It tries the async Clipboard API and
    falls back to a hidden-textarea + execCommand("copy") so it still works
    inside the component iframe. Shows a brief "Copied!" confirmation."""
    payload = json.dumps(text)
    html = f"""
    <div style="font-family:'Source Sans Pro',sans-serif">
      <button id="{key}-btn" style="
          background:#9a3a00;color:#fff;border:0;border-radius:8px;
          padding:9px 16px;font-size:14px;font-weight:600;cursor:pointer;
          box-shadow:0 1px 2px rgba(0,0,0,.25)">{label}</button>
      <span id="{key}-msg" style="margin-left:10px;color:#2f7a52;
          font-size:13px;font-weight:600"></span>
    </div>
    <script>
      const b = document.getElementById("{key}-btn");
      const m = document.getElementById("{key}-msg");
      const txt = {payload};
      b.addEventListener("click", async () => {{
        try {{ await navigator.clipboard.writeText(txt); }}
        catch (e) {{
          const ta = document.createElement("textarea");
          ta.value = txt; ta.style.position = "fixed"; ta.style.opacity = "0";
          document.body.appendChild(ta); ta.focus(); ta.select();
          try {{ document.execCommand("copy"); }} catch (e2) {{}}
          document.body.removeChild(ta);
        }}
        m.textContent = "✓ Copied!";
        b.style.background = "#2f7a52";
        setTimeout(() => {{ m.textContent = ""; b.style.background = "#9a3a00"; }}, 1800);
      }});
    </script>
    """
    components.html(html, height=height)


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
CLASSES = ["equity", "fixed_income", "commodity", "cash"]
# Allocation options shown on the Intake page. The first four are the asset
# classes the parser + suitability engine always understand; FX and structured
# products are the extra two. All six share one 100% target budget, and any of the
# six that carries a target weight drives the suitability engine (allocation bands)
# and the rebalance — see banded_keys(). The engine never fabricates holdings: an
# unheld weighted sleeve simply reads 0% held and is checked/rebalanced to target.
ALLOC_OPTIONS = [
    ("equity", "Equity"), ("fixed_income", "Fixed income"),
    ("commodity", "Commodity"), ("cash", "Cash"),
    ("fx", "FX"), ("structured_products", "Structured products"),
]
ALLOC_KEYS = [k for k, _ in ALLOC_OPTIONS]
EXTRA_ALLOC = ["fx", "structured_products"]  # engine-driven only when weighted
ILLIQ = {"alternatives", "real_estate"}

def banded_keys(target_all: dict) -> list[str]:
    """Asset classes the engine bands: the core four always, plus FX / structured
    products only when the analyst has given them a target weight. Keeps the deck
    and suitability output unchanged when those two sleeves are left at 0%."""
    return CLASSES + [k for k in EXTRA_ALLOC if target_all.get(k, 0)]


PRESETS = {  # target allocation in PERCENT
    "Conservative": {"equity": 20, "fixed_income": 45, "commodity": 5, "cash": 30},
    "Moderate":     {"equity": 35, "fixed_income": 40, "commodity": 5, "cash": 20},
    "Balanced":     {"equity": 50, "fixed_income": 30, "commodity": 10, "cash": 10},
    "Growth":       {"equity": 65, "fixed_income": 20, "commodity": 5, "cash": 10},
    "Aggressive":   {"equity": 80, "fixed_income": 10, "commodity": 5, "cash": 5},
}
SAMPLES = {
    "UOB Private Bank (USD, per-share)": "custodianA_uob.csv",
    "Banque Privée (EUR/CHF, % nominal)": "custodianB_eurobank.csv",
    "Alpine Trust (alts + Lombard)": "custodianC_familyoffice.json",
}
SAMPLE_PDF = {  # formatted "training" statement matching each sample
    "custodianA_uob.csv": "Example_Statement_A_uob.pdf",
    "custodianB_eurobank.csv": "Example_Statement_B_banque_privee.pdf",
    "custodianC_familyoffice.json": "Example_Statement_C_alpine_trust.pdf",
}
SAMPLE_HTML = {  # the formatted statement's HTML source (same layout as the PDF)
    "custodianA_uob.csv": "_statements_html/A_uob.html",
    "custodianB_eurobank.csv": "_statements_html/B_banque_privee.html",
    "custodianC_familyoffice.json": "_statements_html/C_alpine_trust.html",
}
ENFORCE_COLOR = {"block": "#c0563d", "flag": "#c78a2a", "disclose": "#4a9c6d", "none": "#4a9c6d"}
TICKER_BY_ISIN = {"US78462F1030": "SPY", "US46090E1038": "QQQ"}

# DEMO_MODE hides the two features that need API keys / a live network (live-price
# fetch and grounded-Claude phrasing) so the app is a clean, self-contained POC.
# Default ON. Flip it off in production by setting DEMO_MODE=0 as an env var / secret.
DEMO_MODE = os.environ.get("DEMO_MODE", "1").lower() not in ("0", "false", "no", "off")

st.set_page_config(page_title="Meridian Family Office Copilot · v10", page_icon="🏛️",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
  #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
  /* Remove the sidebar collapse/expand arrows — the rail stays pinned open. */
  [data-testid="stSidebarCollapseButton"], [data-testid="collapsedControl"],
  [data-testid="stSidebarCollapsedControl"] { display: none !important; }
  .block-container { padding-top: 2.2rem; max-width: 1180px; }
  h1, h2, h3 { letter-spacing:-.01em; }
  /* Primary "Analyse" button + selected pills — dark orange, legible white text. */
  .stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"],
  button[data-testid="baseButton-primary"] {
    background-color:#9a3a00 !important; border-color:#9a3a00 !important; color:#fff !important; }
  .stButton > button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover,
  button[data-testid="baseButton-primary"]:hover {
    background-color:#7d2f00 !important; border-color:#7d2f00 !important; color:#fff !important; }
  [data-baseweb="tag"] { background-color:#9a3a00 !important; color:#fff !important; }
  section[data-testid="stSidebar"] { background:#0a1330; border-right:1px solid #1e2c55;
    transform: none !important; visibility: visible !important;
    width: 21rem !important; min-width: 21rem !important; margin-left: 0 !important; }
  section[data-testid="stSidebar"] * { color:#c7d0ea; }
  div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
  .brand { font-size:20px; font-weight:700; color:#fff; line-height:1.1; }
  .brand b { color:#c8a24a; }
  .kicker { font-family:ui-monospace,Menlo,monospace; font-size:9.5px; letter-spacing:.16em;
            text-transform:uppercase; color:#c8a24a; }
  .prov { font-family:ui-monospace,Menlo,monospace; font-size:11px; color:#8592b8; }
  .barlab { font-size:13px; margin-bottom:3px; }
  .bartrack { background:#1e2c55; border-radius:5px; height:12px; position:relative; overflow:hidden; }
  .barfill { height:100%; background:#c8a24a; border-radius:5px; }
  .bartgt { position:absolute; top:-2px; height:16px; width:2px; background:#c7d0ea; }
  .pill { font-family:ui-monospace,Menlo,monospace; font-size:11px; font-weight:700;
          padding:2px 9px; border-radius:5px; color:#fff; text-transform:uppercase; }
  .stTabs [data-baseweb="tab-list"] { gap:2px; }
  .stTabs [data-baseweb="tab"] { font-size:14px; }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Parsing (real adapters, dispatched by detected format)
# --------------------------------------------------------------------------- #
def _detect(text: str) -> str:
    try:
        json.loads(text)
        return "c"
    except Exception:
        return "b" if ("categorie;" in text or ";code;" in text) else "a"


def parse_text(text: str, name: str):
    kind = _detect(text)
    suffix = ".json" if kind == "c" else ".csv"
    tmp = Path(tempfile.gettempdir()) / f"fo_upload_{abs(hash(name))}{suffix}"
    tmp.write_text(text)
    if kind == "c":
        return reconcile(parse_custodian_c(tmp))
    if kind == "b":
        return reconcile(parse_csv_generic(tmp, sep=";", decimal_comma=True))
    return reconcile(parse_csv_generic(tmp, sep=",", decimal_comma=False))


def load_sample(fname: str):
    return parse_text((STMT_DIR / fname).read_text(), fname)


# --------------------------------------------------------------------------- #
# Book + profile from current parameters
# --------------------------------------------------------------------------- #
def build_profile(p: dict) -> RiskProfile:
    ta = p.get("target_all", p["target"])
    keys = banded_keys(ta)
    target = {k: ta[k] / 100 for k in keys}
    tol = p["tol"] / 100
    bands = {k: Bands(max(0.0, target[k] - tol), min(1.0, target[k] + tol)) for k in keys}
    excl = [c for c in ("alternatives", "real_estate", "commodity") if p["excl"][c]]
    cons = Constraints(excluded_asset_classes=excl, base_currency="USD",
                       max_unhedged_fx_pct=p["maxfx"] / 100)
    cl = ConcentrationLimits(max_single_fund_pct=p["maxpos"] / 100)
    return RiskProfile(mandate=p["mandate"], allocation_bands=bands, concentration_limits=cl,
                       constraints=cons, min_liquid_pct=p["minliq"] / 100,
                       complex_products_ok=p["complex"] == "Yes")


def build_book(statements, profile) -> Book:
    positions = [q for stt in statements for q in stt.positions]
    liabilities = [lb for stt in statements for lb in stt.liabilities]
    gross = round(sum(q.mv_base for q in positions), 2)
    debt = round(sum(abs(lb["balance"]) for lb in liabilities), 2)
    recon = [(stt.custodian, stt.recon_ok, stt.recon_delta) for stt in statements]
    suit = suitability_check(profile, to_holdings(statements), as_of=TODAY)
    prov = (f"parsed from {len(statements)} custodian statement(s) "
            f"(as of {statements[0].as_of}); non-USD via {FX_SOURCE}")
    return Book(positions, liabilities, gross, debt, round(gross - debt, 2),
                suit, recon, statements[0].as_of, prov)


def rebalance(book: Book, target: dict) -> pd.DataFrame:
    by = {}
    for q in book.positions:
        by[q.asset_class] = by.get(q.asset_class, 0.0) + q.mv_base
    keys = banded_keys(target)
    rows = []
    for c in dict.fromkeys(keys + list(by)):
        before = by.get(c, 0.0)
        unbanded = c not in keys
        t = 0.0 if unbanded else target.get(c, 0.0) / 100
        delta = t * book.gross - before
        if abs(delta) < 1:
            note, direction = "in band", "—"
        elif c in ILLIQ:
            note, direction = "⚠ illiquid — subject to lockup / liquidity event", "sell"
        elif unbanded and before > 0:
            note, direction = "not in mandate target — divest or amend mandate", "sell"
        elif delta > 0:
            note, direction = "top up to target", "buy"
        else:
            note, direction = "trim to target", "sell"
        rows.append({"Class": c.replace("_", " "), "Before": before / book.gross, "Target": t,
                     "Trade (USD)": delta, "After": (0.0 if unbanded else t),
                     "Direction": direction, "Note": note})
    return pd.DataFrame(rows)


def proposal_model(book: Book, params: dict) -> dict:
    """Compute the proposal deck's content from the parsed book — every value
    from the deterministic engine (parser / suitability / rebalancer). Consumed
    by generate_proposal's HTML / PPTX / PDF renderers so all three agree."""
    money = lambda v: f"${v:,.0f}"
    pct = lambda f: f"{f * 100:.1f}%"
    positions = book.positions
    gross, debt, net = book.gross, book.debt, book.net

    alloc: dict[str, float] = {}
    for q in positions:
        alloc[q.asset_class] = alloc.get(q.asset_class, 0.0) + q.mv_base
    liquid = sum(q.mv_base for q in positions if q.asset_class not in ILLIQ)
    # v10.1 — a MACRO OVERLAY tilts the target (deterministic, bounded, provenanced) so
    # the rebalancing recommendation moves with the client's macro view. The drift table
    # and the rebalance both chase the tilted target; suitability bands stay on the base.
    eff_target_all, overlay = macro_overlay.apply_overlay(params["target_all"],
                                                          params.get("macro_overlay"))
    overlay_changes = macro_overlay.changes(params["target_all"], params.get("macro_overlay"))
    keys = banded_keys(eff_target_all)
    target = {k: eff_target_all[k] / 100 for k in keys}

    alloc_rows = []
    for c in dict.fromkeys(keys + list(alloc)):
        cur = alloc.get(c, 0.0)
        w = cur / gross if gross else 0.0
        t = target.get(c)
        drift = "—" if t is None else f"{(w - t) * 100:+.1f} pp"
        alloc_rows.append([c.replace("_", " ").title(), money(cur), pct(w),
                           "no target" if t is None else pct(t), drift])

    reb = rebalance(book, eff_target_all)
    reb_rows = [[str(r["Class"]).title(), f'{r["Before"] * 100:.1f}%', f'{r["Target"] * 100:.1f}%',
                 f'{r["Trade (USD)"]:+,.0f}', str(r["Direction"]), str(r["Note"])]
                for _, r in reb.iterrows()]
    buys = reb.loc[reb["Trade (USD)"] > 1, "Trade (USD)"].sum()
    sells = -reb.loc[reb["Trade (USD)"] < -1, "Trade (USD)"].sum()
    net_trades = buys - sells

    suit_items = [(f.enforcement, f"rule {f.rule} · {f.detail}")
                  for f in book.suit if f.enforcement != "none"]
    dq = [("Reconciliation", f"{c}: parsed vs stated differ by ${d:,.2f}")
          for c, ok, d in book.recon if not ok]
    dq += [("Data flag", f"{q.name}: {fl}") for q in positions for fl in q.flags]

    # Analyst notes for the deterministic deck's section 7 + the LLM's ANALYST
    # GUIDANCE block: sleeve notes + considerations, plus a SHORT pointer to the
    # client's tactical instructions and each document (their FULL text rides in
    # the dedicated prompt blocks below — see the model keys). Kept short here so
    # the deterministic deck stays readable and the doc text isn't duplicated.
    notes = [f"{LABEL_BY_KEY[k]}: {params['notes'][k]}"
             for k in ALLOC_KEYS if params["notes"].get(k)]
    if params.get("considerations"):
        notes.append(f"Additional considerations: {params['considerations']}")
    # v10: tactical instructions pass through as raw text (no classification). A
    # trimmed pointer here; the verbatim text is carried in the prompt block.
    tactical_text = (params.get("tactical_text") or "").strip()
    if tactical_text:
        short = tactical_text.replace("\n", " ")
        short = short[:400] + (" …" if len(short) > 400 else "")
        notes.append(f"Client tactical instructions (verbatim, folded in as guidance, "
                     f"NOT a source of figures): {short}")
    # v9/v10: research / other documents fold in as advisory context — named here
    # (their full text is in the RESEARCH / OTHER DOCUMENTS prompt blocks).
    for d in params.get("reference_docs") or []:
        notes.append(f"Document “{d.get('name', 'document')}” read and folded in as "
                     f"advisory context ({d.get('chars', 0):,} chars; NOT a source of figures).")
    # v10.1 — macro overlay: surface the tilt in the deck notes + prompt so the AI
    # explains WHY the recommendation moved (a deterministic, provenanced tilt).
    overlay_note = macro_overlay.describe(params["target_all"], params.get("macro_overlay"))
    if overlay_note:
        notes.insert(0, overlay_note)
    overlays = [f"{lbl}: target {b:.0f}% → {t:.0f}%" for lbl, b, t in overlay_changes]

    return {
        "title": "Asset Allocation Proposal",
        "subtitle": f"Consolidated Portfolio · {money(net)} net worth",
        "as_of": book.as_of, "prov": book.prov,
        "meta": {"custodians": len({q.custodian for q in positions}),
                 "entities": len({q.entity for q in positions}), "positions": len(positions),
                 "mandate": params["mandate"], "risk": params["risk"],
                 "ability": params["ability"]},
        "custodian_list": sorted({q.custodian for q in positions}),
        "metrics": [("Net worth", money(net)), ("Gross assets", money(gross)),
                    ("Liabilities", money(debt)),
                    ("Leverage (debt/net)", f"{debt / net:.1%}" if net else "—"),
                    ("Liquid assets", pct(liquid / gross) if gross else "—")],
        "gross_str": money(gross),
        "alloc_rows": alloc_rows, "reb_rows": reb_rows,
        "reb_summary": {"buys": money(buys), "sells": money(sells),
                        "net": f"${net_trades:+,.0f}", "selffund": bool(abs(net_trades) < 1000)},
        "gate": worst_enforcement(book.suit), "suit_items": suit_items,
        "data_quality": dq, "analyst_notes": notes, "overlays": overlays,
        "overlay": {"key": overlay.key, "label": overlay.label,
                    "rationale": overlay.rationale, "implementation": overlay.implementation,
                    "changes": overlay_changes},   # (class-label, base%, tilted%) that moved
        # v10 — RAW material carried into the portable prompt (narrative.build_prompt):
        "intake": {  # the full mandate / policy the analyst set on the Intake page
            "mandate": params["mandate"], "risk": params["risk"], "ability": params["ability"],
            "objective": params.get("objective"), "horizon": params.get("horizon"),
            "baseccy": params.get("baseccy"), "complex": params["complex"],
            "usperson": params.get("usperson"), "target_all": params["target_all"],
            "tol": params["tol"], "minliq": params["minliq"], "maxfx": params["maxfx"],
            "maxpos": params["maxpos"], "excl": params["excl"]},
        "holdings": [{"name": q.name, "asset_class": q.asset_class, "currency": q.currency,
                      "mv_base": q.mv_base, "custodian": q.custodian} for q in positions],
        "statement_sources": params.get("statement_sources") or [],
        "research_docs": [d for d in (params.get("research_docs") or []) if d.get("ok")],
        "other_docs": [d for d in (params.get("other_docs") or []) if d.get("ok")],
        "tactical_text": tactical_text,
    }


def resolve_ticker(q) -> str | None:
    if getattr(q, "id_type", None) == "TICKER" and q.identifier:
        return q.identifier
    return TICKER_BY_ISIN.get(q.identifier)


@st.cache_data(ttl=900, show_spinner=False)
def fetch_live(ticker: str) -> dict:
    from datafeed import Feed
    feed = Feed()
    price, fee, dur = (feed.last_close(ticker), feed.expense_ratio(ticker),
                       feed.reference(ticker, "effective_duration", "yr"))
    t = lambda f: f.text() if f.ok else "[SOURCE REQUIRED]"
    return {"price": t(price), "asof": price.as_of or "—", "stale": price.ok and price.stale,
            "src": price.cite(), "fee": t(fee), "dur": t(dur),
            "dur_src": dur.cite() if dur.ok else ""}


def pill(text: str, color: str) -> str:
    return f"<span class='pill' style='background:{color}'>{text}</span>"


def statement_html(path: Path) -> str:
    """Prepare a formatted statement for inline display: drop the red training
    banner, and force a white page so its dark text is legible inside the app's
    dark theme (the statement is styled for a white/print background)."""
    html = path.read_text()
    html = re.sub(r'<div class="sample">.*?</div>', "", html, count=1)
    return html.replace("</head>", "<style>html,body{background:#fff;margin:0;}</style></head>")


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
def apply_preset():
    for c, v in PRESETS[st.session_state["risk"]].items():
        st.session_state[f"t_{c}"] = float(v)


# Limits the analyst can set with EITHER a slider or a numeric box (kept in sync).
LIMITS = {"tol": ("Band tolerance (±)", 5.0, 30.0), "minliq": ("Minimum liquidity", 0.0, 50.0),
          "maxfx": ("Max unhedged FX", 0.0, 60.0), "maxpos": ("Max single position", 10.0, 60.0)}


def _set_limit(key: str, val: float, lo: float, hi: float):
    """Write a clamped value onto the canonical key and both sibling controls."""
    val = min(hi, max(lo, round(val, 1)))
    st.session_state[key] = val
    st.session_state[f"{key}_sl"] = val
    st.session_state[f"{key}_ni"] = val


def _sync_limit(key: str, src: str, lo: float, hi: float):
    """Mirror a limit edited via slider ('sl') or number ('ni') onto the others."""
    _set_limit(key, st.session_state[f"{key}_{src}"], lo, hi)


def linked_limit(key: str, lo: float, hi: float, step: float = 0.5):
    """One row: a numeric box (styled like the allocation-sleeve inputs) next to a
    slider, both bound to the same value (st.session_state[key]) and kept in sync."""
    label = LIMITS[key][0]
    st.session_state.setdefault(f"{key}_sl", st.session_state[key])
    st.session_state.setdefault(f"{key}_ni", st.session_state[key])
    box, sl = st.columns([1, 1.6])
    box.number_input(label, lo, hi, step=step, key=f"{key}_ni", format="%.1f",
                     on_change=_sync_limit, args=(key, "ni", lo, hi))
    sl.slider(label, lo, hi, step=step, format="%.1f%%", key=f"{key}_sl",
              on_change=_sync_limit, args=(key, "sl", lo, hi), label_visibility="hidden")


def init_state():
    defaults = {"risk": "Balanced", "ability": "Medium", "mandate": "advisory",
                "complex": "Yes", "accredited": "Yes",
                "tol": 15.0, "minliq": 10.0, "maxfx": 30.0, "maxpos": 40.0,
                "horizon": 10, "baseccy": "USD", "usperson": "No", "objective": "balanced",
                "excl_alternatives": False, "excl_real_estate": False, "excl_commodity": False,
                "statements": [], "source": "", "live": False, "view": "Intake",
                "other_docs": [], "research_docs": [], "extracted": [],
                "statement_sources": [],
                "t_fx": 0.0, "t_structured_products": 0.0,
                "alloc_notes": "",
                "tactical_text": "", "macro_overlay": "none"}
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    for c, v in PRESETS["Balanced"].items():
        st.session_state.setdefault(f"t_{c}", float(v))
    for k in ALLOC_KEYS:  # per-sleeve free-text notes (v2)
        st.session_state.setdefault(f"note_{k}", "")


init_state()


def policy_is_default() -> bool:
    """True while the mandate, risk and allocation targets are still untouched
    (the out-of-the-box Balanced preset). Used to nudge the analyst to set the
    policy BEFORE pressing Analyse — analysing against the default preset first
    computes drift/suitability the analyst must then redo. See tactical_swimlane_note.html."""
    if st.session_state["mandate"] != "advisory" or st.session_state["risk"] != "Balanced":
        return False
    base = dict(PRESETS["Balanced"], fx=0.0, structured_products=0.0)
    return all(abs(float(st.session_state[f"t_{k}"]) - float(base.get(k, 0.0))) < 1e-6
               for k in ALLOC_KEYS)


@st.cache_data(ttl=3600, show_spinner=False)
def _extract_doc_cached(name: str, data: bytes) -> dict:
    """v9 — cached text extraction (keyed on the file bytes, so a PDF is parsed once)."""
    return doc_extract.extract_text(data, name)


def _read_doc(f) -> dict:
    """Research/Other upload -> {name,size,text,chars,ok,note,...}. Text is read
    deterministically (no API) and folded into the commentary as advisory context."""
    d = dict(_extract_doc_cached(f.name, f.getvalue()))
    d["size"] = f.size
    return d


def _render_doc_status(docs: list[dict]):
    """Show what was extracted from each doc — transparency before it reaches the LLM."""
    for d in docs:
        if d.get("ok"):
            st.markdown(f"<div class='prov'>✅ <b>{d['name']}</b> "
                        f"({d['size'] / 1024:,.0f} KB · {d['chars']:,} chars read"
                        + (" · truncated" if d.get("truncated") else "") + ")</div>",
                        unsafe_allow_html=True)
            with st.expander(f"Text folded in — {d['name']}", expanded=False):
                st.text((d.get("text") or "")[:2000]
                        + (" …" if len(d.get("text") or "") > 2000 else ""))
        else:
            st.markdown(f"<div class='prov'>⚠️ <b>{d['name']}</b> "
                        f"({d['size'] / 1024:,.0f} KB) — not read: {d.get('note', '')}. "
                        "Name recorded; content not sent to the copilot.</div>",
                        unsafe_allow_html=True)


def _doc_staging_status(uploader_key: str, committed_key: str):
    """v10: uploaded research / other files are STAGED, not processed. They are only
    read and folded into the analysis when the user presses Analyse — so uploading
    or removing a file incurs no processing/cost until then. Show the committed
    (already-read) docs, and flag when the staged uploads differ from them."""
    staged = st.session_state.get(uploader_key) or []
    committed = st.session_state.get(committed_key, [])
    if {f.name for f in staged} != {d.get("name") for d in committed}:
        if staged:
            st.markdown(f"<div class='prov'>📎 <b>{len(staged)} file(s) staged</b> — press "
                        "<b>Analyse ▸</b> to read &amp; include them. Nothing is processed "
                        "until you do.</div>", unsafe_allow_html=True)
        elif committed:
            st.markdown("<div class='prov'>Uploads changed — press <b>Analyse ▸</b> to update "
                        "the included set.</div>", unsafe_allow_html=True)
    _render_doc_status(committed)


# --------------------------------------------------------------------------- #
# Sidebar — brand + live status (nav is the tabs)
# --------------------------------------------------------------------------- #
statements = st.session_state["statements"]

with st.sidebar:
    st.markdown("<div class='brand'>Meridian<br><b style='font-size:13px'>Family Office</b>"
                "<span style='font-size:11px;color:#9a3a00;font-weight:700;margin-left:6px'>v10</span>"
                "</div>", unsafe_allow_html=True)
    st.markdown("<div class='kicker'>AI Copilot · Confidential</div>", unsafe_allow_html=True)
    st.divider()
    st.markdown("##### 1 · Client documents")
    up = st.file_uploader(
        "Upload statements — PDF / image, or tuned .csv / .json",
        type=["pdf", "png", "jpg", "jpeg", "csv", "json"], accept_multiple_files=True)
    ex_key = resolve_key("ANTHROPIC_API_KEY") or resolve_key("API_KEY_260627")
    extract_on = (not DEMO_MODE) and bool(ex_key)
    st.caption(
        "PDF / image statements are read by a vision model that transcribes the holdings "
        "for you to review — this needs an API key (set DEMO_MODE=0). "
        + ("✅ enabled." if extract_on
           else "🔒 off in this demo build — upload the tuned .csv / .json instead."))
    picks = st.pills("…or load example client statements", list(SAMPLES.keys()),
                     selection_mode="multi") or []
    b1, b2 = st.columns(2)
    if b1.button("Analyse ▸", type="primary", use_container_width=True):
        sts, labels, pending, sources = [], [], [], []
        for f in (up or []):
            ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
            if ext in ("csv", "json"):
                try:
                    raw = f.getvalue().decode("utf-8", "replace")
                    sts.append(parse_text(raw, f.name))
                    labels.append(f.name)
                    sources.append({"name": f.name, "text": raw})  # v10: raw source for the prompt
                except Exception as e:  # noqa: BLE001
                    st.error(f"{f.name}: {type(e).__name__} — {e}")
            elif not extract_on:
                st.warning(f"{f.name}: PDF/image ingestion needs an API key (DEMO_MODE=0). "
                           "Upload the tuned .csv / .json instead.")
            else:
                try:
                    data = vision_extract.extract(f.getvalue(), f.name, ex_key)
                    pending.append({"name": f.name, "data": data})
                except Exception as e:  # noqa: BLE001
                    st.error(f"{f.name}: extraction failed — {type(e).__name__}: {e}")
        for label in picks:
            fname = SAMPLES[label]
            sts.append(load_sample(fname))
            labels.append(fname)
            sources.append({"name": fname, "text": (STMT_DIR / fname).read_text()})
        st.session_state["extracted"] = pending
        # v10: read & COMMIT the research / other documents ONLY here, on Analyse —
        # never automatically on upload. Uploading (or removing) a file does nothing
        # until the user presses Analyse, so no processing/cost is incurred on a
        # change of mind. Read from the uploader widgets' persisted session state
        # (this handler runs before the uploaders are re-instantiated this run).
        st.session_state["research_docs"] = [
            _read_doc(f) for f in (st.session_state.get("research_uploader") or [])]
        st.session_state["other_docs"] = [
            _read_doc(f) for f in (st.session_state.get("other_uploader") or [])]
        if sts:
            st.session_state["statements"] = sts
            st.session_state["source"] = ", ".join(labels)
            st.session_state["statement_sources"] = sources
            st.session_state["live"] = False
            # Stay on Intake to review any transcribed PDF/image statements first.
            st.session_state["view"] = "Intake" if pending else "Overview"
            st.rerun()
        elif pending:
            st.session_state["view"] = "Intake"
            st.rerun()
        elif st.session_state.get("statements"):
            # A book is already loaded; Analyse just (re)committed the documents.
            st.rerun()
        else:
            st.warning("Add at least one document first.")
    if b2.button("Clear", use_container_width=True):
        st.session_state["statements"] = []
        st.session_state["extracted"] = []
        st.session_state["statement_sources"] = []
        st.session_state["research_docs"] = []
        st.session_state["other_docs"] = []
        st.session_state["live"] = False
        st.session_state["view"] = "Intake"
        st.rerun()

    if not statements and policy_is_default():
        st.caption("💡 Set the **mandate, risk & allocation targets** on the Intake "
                   "tab first — then Analyse, so the first read already reflects the "
                   "client's policy (not the default Balanced preset).")

    if statements:
        st.success(f"Loaded: {st.session_state['source']}")
        st.divider()
        params_preview = {"mandate": st.session_state["mandate"], "risk": st.session_state["risk"],
                          "complex": st.session_state["complex"], "tol": st.session_state["tol"],
                          "minliq": st.session_state["minliq"], "maxfx": st.session_state["maxfx"],
                          "maxpos": st.session_state["maxpos"],
                          "target": {c: st.session_state[f"t_{c}"] for c in CLASSES},
                          "target_all": {k: st.session_state[f"t_{k}"] for k in ALLOC_KEYS},
                          "excl": {c: st.session_state[f"excl_{c}"]
                                   for c in ("alternatives", "real_estate", "commodity")}}
        _book = build_book(statements, build_profile(params_preview))
        _gate = worst_enforcement(_book.suit)
        st.metric("Net worth", f"${_book.net:,.0f}")
        st.metric("Gross assets", f"${_book.gross:,.0f}")
        st.markdown(f"Suitability gate&nbsp; {pill(_gate, ENFORCE_COLOR[_gate])}",
                    unsafe_allow_html=True)
        st.markdown(f"<div class='prov'>{_book.prov}</div>", unsafe_allow_html=True)
    else:
        st.info("Add documents above and press **Analyse ▸** to begin.")

    # --- Research documents (v4): formal research — extra context ----------- #
    st.divider()
    st.markdown("##### 2 · Research documents")
    st.caption("Formal research — house or third-party investment research, factsheets, "
               "strategy and market reports. On **Analyse** their full text is read and passed "
               "to the AI as advisory context in the prompt — never as a source of figures.")
    research = st.file_uploader(
        "Upload research reports, factsheets (.pdf / .docx / .txt / .md / .html)",
        type=["pdf", "docx", "doc", "txt", "md", "html", "rtf"],
        accept_multiple_files=True, key="research_uploader")
    _doc_staging_status("research_uploader", "research_docs")

    # --- Other documents (v2): emails, notes — informal context ------------- #
    st.divider()
    st.markdown("##### 3 · Other documents")
    st.caption("Informal context — emails, meeting notes and correspondence. On **Analyse** the "
               "text is read and passed to the AI as advisory context in the prompt, alongside "
               "the statements.")
    other = st.file_uploader(
        "Upload emails, notes (.pdf / .docx / .txt / .md / .eml / .msg)",
        type=["pdf", "docx", "doc", "txt", "md", "eml", "msg", "rtf", "html", "png", "jpg"],
        accept_multiple_files=True, key="other_uploader")
    _doc_staging_status("other_uploader", "other_docs")

    st.divider()
    st.markdown("##### Navigate")
    st.radio("Navigate", ["Intake", "Sample statements", "Overview", "Holdings", "Suitability",
                          "Data quality", "Proposal", "Ask the book"],
             key="view", label_visibility="collapsed")


# --------------------------------------------------------------------------- #
# Main — view dispatch (navigation lives in the sidebar rail)
# --------------------------------------------------------------------------- #
st.title("Family Office Copilot")

params = {"mandate": st.session_state["mandate"], "risk": st.session_state["risk"],
          "ability": st.session_state["ability"],
          "objective": st.session_state["objective"], "horizon": st.session_state["horizon"],
          "baseccy": st.session_state["baseccy"], "usperson": st.session_state["usperson"],
          "complex": st.session_state["complex"], "tol": st.session_state["tol"],
          "minliq": st.session_state["minliq"], "maxfx": st.session_state["maxfx"],
          "maxpos": st.session_state["maxpos"],
          "target": {c: st.session_state[f"t_{c}"] for c in CLASSES},
          "target_all": {k: st.session_state[f"t_{k}"] for k in ALLOC_KEYS},
          "notes": {k: st.session_state[f"note_{k}"].strip() for k in ALLOC_KEYS},
          "considerations": st.session_state["alloc_notes"].strip(),
          # v10 — tactical instructions pass through as RAW text (no classification)
          "tactical_text": st.session_state.get("tactical_text", "").strip(),
          "macro_overlay": st.session_state.get("macro_overlay", "none"),
          "statement_sources": st.session_state.get("statement_sources", []),
          "research_docs": st.session_state.get("research_docs", []),
          "other_docs": st.session_state.get("other_docs", []),
          "reference_docs": [d for d in (st.session_state.get("research_docs", [])
                                         + st.session_state.get("other_docs", [])) if d.get("ok")],
          "excl": {c: st.session_state[f"excl_{c}"]
                   for c in ("alternatives", "real_estate", "commodity")}}
book = build_book(statements, build_profile(params)) if statements else None
view = st.session_state["view"]


def analyst_inputs_present() -> bool:
    """Any of the free-text notes / tactical instructions / research / other-docs?"""
    return (any(params["notes"].values())
            or bool(params.get("considerations"))
            or bool(params.get("tactical_text"))
            or bool(st.session_state.get("research_docs"))
            or bool(st.session_state.get("other_docs")))


def render_analyst_inputs():
    """Surface the captured notes, tactical instructions and attachments — the human
    context the copilot passes to the AI (never invented into figures)."""
    notes = {LABEL_BY_KEY[k]: v for k, v in params["notes"].items() if v}
    research = st.session_state.get("research_docs", [])
    docs = st.session_state.get("other_docs", [])

    def _docline(d):
        return (f"{d['name']} — *folded in as context ({d['chars']:,} chars)*" if d.get("ok")
                else f"{d['name']} — *name only; content not read*")
    if research:
        st.markdown("**Research documents:** " + " · ".join(_docline(d) for d in research))
    if docs:
        st.markdown("**Other documents:** " + " · ".join(_docline(d) for d in docs))
    for label, text in notes.items():
        st.markdown(f"- **{label} note:** {text}")
    if params.get("considerations"):
        st.markdown(f"**Additional considerations:** {params['considerations']}")
    if params.get("tactical_text"):
        st.markdown("**📝 Client tactical instructions** — passed to the AI verbatim as "
                    "context (never a source of figures):")
        st.markdown(f"> {params['tactical_text'].replace(chr(10), chr(10) + '> ')}")


LABEL_BY_KEY = dict(ALLOC_OPTIONS)

_REVIEW_COLS = ["name", "asset_class", "currency", "market_value_ccy",
                "identifier", "id_type", "instrument_type"]


def render_extraction_review():
    """v5: review + confirm PDF/image statements the vision model transcribed.

    The model only transcribed printed figures; here the analyst checks them
    against the original and edits any misread, then the DETERMINISTIC engine
    (parse_extracted -> reconcile) converts currencies and reconciles against the
    printed total. Nothing joins the book until the analyst confirms."""
    pending = st.session_state.get("extracted", [])
    if not pending:
        return
    st.divider()
    st.markdown("##### Review transcribed statements (PDF / image)")
    st.caption("A vision model transcribed these holdings from your uploaded document(s) — it "
               "copied printed figures only. Check them against the original, edit any misread "
               "value, then confirm. The engine converts currencies to USD and reconciles "
               "against the printed total; no figure is computed until you confirm.")
    for i, item in enumerate(pending):
        d = item["data"]
        with st.container(border=True):
            st.markdown(f"**{item['name']}** — {d.get('custodian') or '(custodian n/a)'} · "
                        f"base {d.get('base_currency', 'USD')} · as of {d.get('as_of') or 'n/a'}")
            df = pd.DataFrame(d.get("positions", []) or [], columns=_REVIEW_COLS)
            edited = st.data_editor(df, key=f"edit_{i}", num_rows="dynamic",
                                    use_container_width=True)
            stated = st.number_input(
                f"Printed statement total ({d.get('base_currency', 'USD')})",
                value=float(d.get("stated_total_usd") or 0.0), key=f"stated_{i}")
            recs = edited.to_dict("records")
            cd = {**d, "positions": recs, "stated_total_usd": stated}
            try:
                st_obj = reconcile(parse_extracted(cd))
                parsed = sum(p.mv_base for p in st_obj.positions)
                rec = "✅ OK" if st_obj.recon_ok else f"⚠️ Δ ${st_obj.recon_delta:,.2f}"
                st.caption(f"{len(recs)} positions · parsed ${parsed:,.2f} (USD) · "
                           f"stated ${st_obj.stated_total:,.2f} · reconciliation {rec}")
                ok = True
            except Exception as e:  # noqa: BLE001
                st.error(f"Cannot parse yet — {type(e).__name__}: {e}")
                st_obj, ok = None, False
            bc = st.columns(2)
            if bc[0].button("✓ Confirm & add to book", key=f"conf_{i}", type="primary",
                            disabled=not ok):
                st.session_state["statements"] = st.session_state["statements"] + [st_obj]
                src = st.session_state.get("source", "")
                st.session_state["source"] = (src + ", " if src else "") + item["name"]
                st.session_state["extracted"] = [x for j, x in enumerate(pending) if j != i]
                st.rerun()
            if bc[1].button("✕ Discard", key=f"disc_{i}"):
                st.session_state["extracted"] = [x for j, x in enumerate(pending) if j != i]
                st.rerun()


def need_book():
    st.info("👈 Load the client's documents in the sidebar and press **Analyse ▸** first.")


# ---- Intake (parameters; documents live in the sidebar) ---- #
if view == "Intake":
    st.caption("Set the mandate, risk appetite and parameters. Load documents in the sidebar, "
               "then Analyse — every view recomputes from the real engines.")
    render_extraction_review()
    c2, c3 = st.columns(2, gap="large")
    with c2:
        st.markdown("##### Mandate & risk")
        st.selectbox("Mandate", ["execution_only", "advisory", "discretionary"], key="mandate")
        st.selectbox("Risk appetite", list(PRESETS.keys()), key="risk", on_change=apply_preset)
        st.caption("Willingness to take risk — drives the target allocation preset above.")
        st.selectbox("Ability to take risk",
                     ["Low", "Below average", "Medium", "Above average", "High"], key="ability")
        st.caption("Capacity to absorb loss (liquidity, horizon, income) — independent of "
                   "appetite; the lower of the two should govern.")
        st.selectbox("Objective", ["preservation", "income", "balanced", "growth"], key="objective")
        cc = st.columns(2)
        cc[0].number_input("Time horizon (yrs)", 1, 40, key="horizon")
        cc[1].selectbox("Base currency", ["USD", "EUR", "CHF", "SGD"], key="baseccy")
        st.radio("Complex products allowed?", ["Yes", "No"], horizontal=True, key="complex")
        st.radio("US person? (tax)", ["No", "Yes"], horizontal=True, key="usperson")
    with c3:
        st.markdown("##### Allocation & limits")
        st.caption("Target weight and a free-text note per sleeve. All six sleeves share one "
                   "100% budget; any sleeve with a target weight — including FX and structured "
                   "products — drives the live suitability engine and the rebalance.")
        tot = 0.0
        for k, label in ALLOC_OPTIONS:
            row = st.columns([1, 1.6])
            row[0].number_input(label, 0.0, 100.0, step=0.1, key=f"t_{k}")
            row[1].text_input(f"{label} note", key=f"note_{k}", label_visibility="hidden",
                              placeholder=f"Notes on {label.lower()}…")
            tot += st.session_state[f"t_{k}"]
        (st.success if abs(tot - 100) < 0.05 else st.error)(f"Target total (6 sleeves) {tot:.1f}%")

        st.text_area("Additional considerations for the analysis", key="alloc_notes",
                     placeholder="Anything else the copilot should weigh — constraints, client "
                                 "preferences, upcoming liquidity events, tax or regulatory notes…")
        st.caption("Each limit takes a slider **or** the numeric box beside it — they stay in sync.")
        for _k, (_lo, _hi) in {"tol": (5.0, 30.0), "minliq": (0.0, 50.0),
                               "maxfx": (0.0, 60.0), "maxpos": (10.0, 60.0)}.items():
            linked_limit(_k, _lo, _hi)
        st.markdown("**Exclusions (won't hold)**")
        ec = st.columns(3)
        ec[0].checkbox("Alternatives", key="excl_alternatives")
        ec[1].checkbox("Real estate", key="excl_real_estate")
        ec[2].checkbox("Commodities", key="excl_commodity")

    # ---- Tactical instructions (v10): free text passed straight to the AI ---- #
    st.divider()
    st.markdown("##### Tactical instructions")
    st.caption("Ad-hoc client guidance in plain language — e.g. *“buy the bond fund in "
               "tranches”*, *“add Nasdaq only after a 15–20% pullback”*, *“gold below "
               "USD 4,000/oz”*, *“low fees and good liquidity”*. v10: these are **no longer "
               "sorted into items** — the copilot passes them **verbatim** to the AI, alongside "
               "the intake parameters, the client holdings and the research / other documents, "
               "so the AI analyses them directly. They are context for the write-up, never a "
               "source of computed figures — every number still comes from the engine.")
    st.text_area("Client tactical instructions (free text)", key="tactical_text", height=150,
                 placeholder="Paste or type the client's tactical asks in plain language…")
    st.caption("These flow into the **prompt on the Proposal page** — where you (and the client) "
               "can read the exact prompt, copy it, and test it with alternative LLMs.")

    # ---- Macro overlay (v10.1): a named macro view that MOVES the numbers ---- #
    st.divider()
    st.markdown("##### Macro overlay — move the numbers, not just the words")
    st.caption("Optionally apply a client **macro view** as a deterministic, bounded tilt to the "
               "target allocation. Unlike the tactical text (which shapes the write-up), this "
               "**re-weights the target so the rebalancing recommendation shifts** — e.g. *rate "
               "cuts* → deploy cash into bonds; *risk-off* → raise gold & cash, trim equity. The "
               "tilt is a fixed, documented rule (never model-invented) and sums to zero; the "
               "suitability bands stay on the strategic policy.")
    _ov_labels = {k: l for k, l in macro_overlay.options()}
    st.selectbox("Apply a macro overlay", list(_ov_labels), key="macro_overlay",
                 format_func=lambda k: _ov_labels.get(k, k))
    _ov_changes = macro_overlay.changes(
        {k: st.session_state[f"t_{k}"] for k in ALLOC_KEYS}, st.session_state["macro_overlay"])
    if _ov_changes:
        _mv = " · ".join(f"{lbl} {b:.0f}%→{t:.0f}%" for lbl, b, t in _ov_changes)
        st.markdown(f"<div class='prov'>↕ Target tilt: {_mv}</div>", unsafe_allow_html=True)
        st.caption(macro_overlay.OVERLAYS[st.session_state["macro_overlay"]].implementation)

    if analyst_inputs_present():
        st.divider()
        st.markdown("##### Analyst inputs the copilot will pass to the AI")
        st.caption("Free-text notes, tactical instructions and attached documents — passed to the "
                   "AI as human context. Figures are never invented from them.")
        render_analyst_inputs()
    # Next-step hand-off (state-aware). The deck needs a parsed book, so a missing
    # book routes to Analyse rather than to an empty Proposal view.
    if statements:
        st.success("✅ **Next:** open **Proposal** in the sidebar — the prompt there bundles your "
                   "inputs, the holdings and the documents for the AI. (Or review **Overview / "
                   "Suitability** first; every view recomputes live as you adjust the parameters.)")
    elif analyst_inputs_present():
        st.info("⏳ **Next:** load the client's documents in the sidebar and press **Analyse ▸** — "
                "the proposal is built from the parsed statements. Your inputs above are saved and "
                "will be passed to the AI once a book is loaded.")

# ---- Sample statements (view the raw inputs; no digested book required) ---- #
elif view == "Sample statements":
    st.caption("The built-in **tuned** example statements — realistic custodian statements with "
               "client PII (names, addresses, account numbers, RM) removed but the holdings "
               "intact. This is exactly what the app ingests.")
    label = st.selectbox("Example statement", list(SAMPLES.keys()))
    fname = SAMPLES[label]

    html_path = Path(__file__).parent / SAMPLE_HTML.get(fname, "")
    if html_path.is_file():
        st.markdown("**Formatted statement** — the same layout as the PDF, rendered inline:")
        components.html(statement_html(html_path), height=900, scrolling=True)

    pdf = Path(__file__).parent / SAMPLE_PDF.get(fname, "")
    if pdf.is_file():
        st.download_button("⬇ Download this statement as a PDF", pdf.read_bytes(),
                           file_name=pdf.name, mime="application/pdf")

    with st.expander("Show the raw source the parser reads (CSV / JSON)"):
        raw = (STMT_DIR / fname).read_text()
        st.caption(f"Source file: `{fname}`")
        if fname.endswith(".json"):
            st.json(json.loads(raw))
        else:
            st.code(raw, language="text")

    with st.expander("See how the app parses this into positions"):
        stt = load_sample(fname)
        rows = [{"Holding": p.name, "Class": p.asset_class, "Ccy": p.currency,
                 "Value (USD)": p.mv_base} for p in stt.positions]
        st.dataframe(pd.DataFrame(rows).style.format({"Value (USD)": "${:,.0f}"}),
                     use_container_width=True, hide_index=True)
        st.caption("Parsed by the same real adapter used on the Intake flow.")

# ---- Proposal (deck GENERATED from the parsed book + PPTX / PDF download) ---- #
elif view == "Proposal":
    if not book:
        st.info("👈 Load the client's documents in the sidebar and press **Analyse ▸** — the "
                "proposal deck is generated from the parsed book.")
    else:
        st.caption("The recommendation, built from the loaded statements. The tables and every "
                   "figure are computed by the deterministic engine from the client's holdings "
                   "(nothing is invented); the AI reads the prompt below — parameters, holdings, "
                   "documents and the client's tactical instructions — and writes the proposal "
                   "narrative around those figures.")
        model = proposal_model(book, params)

        # v10.1 — if a macro overlay is active, show that it MOVED the recommendation
        # (the tilted target the rebalance chased) — deterministic and provenanced.
        _ov = model.get("overlay") or {}
        if _ov.get("changes"):
            _mv = " · ".join(f"**{lbl}** {b:.0f}% → {t:.0f}%" for lbl, b, t in _ov["changes"])
            st.info(f"↕ **Macro overlay applied — {_ov['label']}.** Target tilt: {_mv}. "
                    f"{_ov['rationale']} The rebalancing below chased this tilted target, so the "
                    f"recommendation moved with the view; every figure stays deterministic and the "
                    f"suitability bands remain on the strategic policy.")

        # ---- v10: THE PROMPT — the focused instruction that generates the deck's
        #           CIO commentary. Surfaced so the client can read it, edit it, copy
        #           it, and test it with alternative LLMs. It asks ONLY for the
        #           commentary prose (not a whole deck), so the returned text drops
        #           cleanly onto the commentary slide. --- #
        narr_key = resolve_key("ANTHROPIC_API_KEY") or resolve_key("API_KEY_260627")
        llm_on = (not DEMO_MODE) and bool(narr_key)
        # Keep the shown prompt in step with the current inputs (FACTS + parameters +
        # committed docs + tactical text all fold into it).
        _fresh_prompt = narrative.build_commentary_prompt(model)
        if "narr_prompt" not in st.session_state:
            st.session_state["narr_prompt"] = _fresh_prompt

        st.markdown("### 🧠 The prompt handed to the AI")
        st.caption(
            "The **self-contained prompt** the copilot sends to the model to write the "
            "**Investment Commentary** — the grounding rule, the deterministic FACTS (the only "
            "source of numbers), the intake parameters, the parsed holdings, the research / other "
            "documents in full and the client's tactical instructions verbatim. It asks for the "
            "commentary prose only. Read it, edit it, copy it, and paste it into **any** AI model.")
        pc = st.columns([1, 1, 2])
        if pc[0].button("↻ Rebuild prompt from current inputs"):
            st.session_state["narr_prompt"] = _fresh_prompt
            st.rerun()
        if st.session_state["narr_prompt"] != _fresh_prompt:
            pc[1].caption("✎ prompt edited or inputs changed — Rebuild to refresh")
        st.text_area(
            "Prompt (editable — edit freely before generating or copying)",
            key="narr_prompt", height=340,
            help="The FACTS block is the only source of numbers; the parameters, documents and "
                 "tactical instructions are intent and context, not figures.")
        copy_button(st.session_state["narr_prompt"], "📋 Copy prompt to clipboard",
                    key="copy_prompt")
        st.download_button("⬇ Download prompt (.txt)", st.session_state["narr_prompt"],
                           file_name="Meridian_commentary_prompt.txt", mime="text/plain")

        # The portable WHOLE-DECK prompt — a separate artifact for reproducing the
        # entire deck in any LLM. Not used to generate the commentary above.
        with st.expander("📄 Full deck-reproduction prompt (optional) — paste into any LLM to "
                         "rebuild the entire deck"):
            deck_prompt = narrative.build_prompt(model)
            st.caption("This asks an LLM to reproduce the **whole** proposal deck as a file. It is "
                       "**not** what writes the commentary here — it's provided so you can "
                       "regenerate the full deck elsewhere.")
            st.code(deck_prompt, language="text")
            st.download_button("⬇ Download full deck prompt (.txt)", deck_prompt,
                               file_name="Meridian_full_deck_prompt.txt", mime="text/plain",
                               key="dl_deck_prompt")

        st.divider()
        st.markdown("### ✨ Proposal commentary — writes from your inputs & documents")

        # The commentary folds the research / other documents and the tactical
        # instructions into the DELIVERABLE. It generates ONLY when the user presses the
        # button below — never automatically — so no model call (and no cost) is incurred
        # on upload or navigation. Every figure stays deterministic regardless.
        prompt = st.session_state["narr_prompt"]
        phash = hashlib.md5(prompt.encode("utf-8")).hexdigest()

        def _generate():
            """Return (text, src). Runs the live model when on, else the grounded summary."""
            if llm_on:
                try:
                    return narrative.generate_claude(prompt, narr_key)
                except Exception as e:  # noqa: BLE001
                    st.warning(f"AI model unavailable ({type(e).__name__}) — using the "
                               "deterministic grounded summary.")
            return narrative.deterministic_summary(model), "deterministic"

        have_narr = bool(st.session_state.get("narrative_text"))
        bc = st.columns([1, 1, 2])
        gen_label = "↻ Regenerate commentary" if have_narr else "✨ Generate commentary"
        gen = bc[0].button(gen_label, type="primary")
        if gen:
            spin = ("Writing the proposal commentary from your inputs & documents…"
                    if llm_on else "Assembling the grounded commentary…")
            with st.spinner(spin):
                text, src = _generate()
            st.session_state["narrative_text"] = text
            st.session_state["narrative_src"] = src
            st.session_state["narrative_phash"] = phash
            st.rerun()

        if llm_on:
            st.caption("Nothing is sent to the model until you press **Generate** — it then writes "
                       "the commentary from your inputs, documents and tactical instructions and "
                       "folds it into the deck. The model may quote the FACTS figures but never "
                       "invents or alters them; the tables and downloads stay deterministic.")
        else:
            st.caption("🔒 Live AI model off (demo mode / no API key): **Generate** assembles a "
                       "**deterministic** grounded summary that still reflects your documents & "
                       "tactical instructions as context. Set `DEMO_MODE=0` with an API key for the "
                       "live model to synthesise them fully. The prompt above works in any AI model.")

        if st.session_state.get("narrative_text"):
            src = st.session_state.get("narrative_src", "deterministic")
            badge = ("AI Model" if src == "claude"
                     else "deterministic fallback (no model call)")
            st.markdown(f"**Proposal commentary** · _{badge}_")
            if st.session_state.get("narrative_phash") != phash:
                st.info("Inputs or the prompt changed since this was written — press "
                        "**Regenerate commentary** to refresh it.")
            st.write(st.session_state["narrative_text"])
            st.caption("Folded into the deck below and the PPTX/PDF downloads as a commentary "
                       "slide after the cover.")
            st.caption("⚖️ Every figure remains computed by the deterministic engine. The "
                       "narrative's **qualitative** statements draw on the client's documents "
                       "and instructions supplied to the model as context and are **not "
                       "independently verified** — for discussion only, not investment advice.")
            if bc[1].button("✕ Clear commentary"):
                st.session_state.pop("narrative_text", None)
                st.session_state.pop("narrative_src", None)
                st.session_state.pop("narrative_phash", None)
                st.rerun()
            model["narrative"] = st.session_state["narrative_text"]
        st.divider()

        stem = "Portfolio_Proposal_" + re.sub(r"[^A-Za-z0-9]+", "_",
                                               st.session_state.get("source", "book"))[:40]
        d1, d2, _ = st.columns([1, 1, 2])
        try:
            d1.download_button("⬇ Download PPTX", generate_proposal.render_pptx(model),
                               file_name=f"{stem}.pptx", use_container_width=True,
                               mime="application/vnd.openxmlformats-officedocument."
                                    "presentationml.presentation")
            d2.download_button("⬇ Download PDF", generate_proposal.render_pdf(model),
                               file_name=f"{stem}.pdf", mime="application/pdf",
                               use_container_width=True)
        except Exception as e:  # noqa: BLE001
            st.error(f"Deck export unavailable: {type(e).__name__} — {e}. "
                     "Add `python-pptx` and `reportlab` to requirements.txt.")

        if analyst_inputs_present():
            with st.expander("Analyst inputs folded into this proposal"):
                render_analyst_inputs()

        st.markdown("**Proposal deck** — generated from the parsed book (identical to the "
                    "downloads above):")
        components.html(generate_proposal.render_html(model), height=760, scrolling=True)

elif not book:
    need_book()

# ---- Overview ---- #
elif view == "Overview":
    breaches = [f for f in book.suit if f.enforcement in ("block", "flag")]
    dq = [(c, ok, d) for c, ok, d in book.recon if not ok] + \
         [(q.name, fl) for q in book.positions for fl in q.flags]
    liq = sum(q.mv_base for q in book.positions if q.asset_class not in ILLIQ)
    k = st.columns(4)
    k[0].metric("Net worth", f"${book.net:,.0f}")
    k[1].metric("Gross assets", f"${book.gross:,.0f}")
    k[2].metric("Leverage", f"{book.debt / book.net:.1%}" if book.net else "—")
    k[3].metric("Liquid", f"{liq / book.gross:.1%}")

    st.subheader("Allocation — actual vs target")
    by = {}
    for q in book.positions:
        by[q.asset_class] = by.get(q.asset_class, 0.0) + q.mv_base
    keys = banded_keys(params["target_all"])
    target = {k: params["target_all"][k] / 100 for k in keys}
    for c in dict.fromkeys(keys + list(by)):
        w = by.get(c, 0.0) / book.gross
        t = target.get(c, 0.0)
        tgt = f"<div class='bartgt' style='left:{min(100, t * 100):.0f}%'></div>" if t else ""
        st.markdown(
            f"<div class='barlab'>{c.replace('_', ' ')} — {w:.1%}"
            f"{' · tgt ' + format(t, '.0%') if t else ' · no target'}</div>"
            f"<div class='bartrack'><div class='barfill' style='width:{min(100, w * 100):.0f}%'>"
            f"</div>{tgt}</div>", unsafe_allow_html=True)
        st.write("")

    st.subheader("Needs attention")
    if not breaches and not dq:
        st.success("Nothing needs attention.")
    for f in breaches:
        st.markdown(f"{pill(f.enforcement, ENFORCE_COLOR[f.enforcement])}&nbsp; {f.detail}",
                    unsafe_allow_html=True)
    for item in dq:
        detail = f"{item[0]}: Δ ${item[2]:,.2f}" if len(item) == 3 else f"{item[0]}: {item[1]}"
        st.markdown(f"{pill('review', '#c78a2a')}&nbsp; {detail}", unsafe_allow_html=True)

# ---- Holdings ---- #
elif view == "Holdings":
    rows = [{"Custodian": q.custodian, "Entity": q.entity, "Holding": q.name,
             "Class": q.asset_class, "Ccy": q.currency, "Value (USD)": q.mv_base,
             "Flags": " · ".join(q.flags) if q.flags else ""} for q in book.positions]
    st.dataframe(pd.DataFrame(rows).style.format({"Value (USD)": "${:,.0f}"}),
                 use_container_width=True, hide_index=True)
    st.caption(f"{len(book.positions)} positions · "
               f"{len({q.custodian for q in book.positions})} custodians · "
               f"{len({q.entity for q in book.positions})} entities.")

    if not DEMO_MODE:
        st.divider()
        st.subheader("Live market data")
        st.caption("Prices & fees from yfinance; effective duration from the verified reference "
                   "table. Anything the free feed can't source shows **[SOURCE REQUIRED]** — never "
                   "a guess. (Needs internet; otherwise everything degrades to [SOURCE REQUIRED].)")
        if st.button("Fetch live prices, fees & durations"):
            st.session_state["live"] = True
        if st.session_state.get("live"):
            live_rows, prov = [], []
            with st.spinner("Querying yfinance / reference table…"):
                for q in book.positions:
                    tk = resolve_ticker(q)
                    if not tk:
                        live_rows.append({"Holding": q.name, "Ticker": "—",
                                          "Live price": "[SOURCE REQUIRED]", "As of": "—",
                                          "Expense ratio": "[SOURCE REQUIRED]",
                                          "Eff. duration": "[SOURCE REQUIRED]"})
                        prov.append(f"**{q.name}** — not exchange-listed / no ticker mapping")
                        continue
                    d = fetch_live(tk)
                    live_rows.append({"Holding": q.name, "Ticker": tk,
                                      "Live price": d["price"] + (" ⚠stale" if d["stale"] else ""),
                                      "As of": d["asof"], "Expense ratio": d["fee"],
                                      "Eff. duration": d["dur"]})
                    prov.append(f"**{tk}** price — {d['src']}"
                                + (f"; duration — {d['dur_src']}" if d["dur_src"] else ""))
            st.dataframe(pd.DataFrame(live_rows), use_container_width=True, hide_index=True)
            with st.expander("Provenance for each live figure"):
                for line in prov:
                    st.markdown(f"- {line}")

# ---- Suitability ---- #
elif view == "Suitability":
    st.caption(f"Checked against the mandate bands · worst action: "
               f"**{worst_enforcement(book.suit)}**")
    shown = [f for f in book.suit if f.enforcement != "none"]
    if not shown:
        st.success("Book is within all defined suitability bands.")
    for f in shown:
        st.markdown(f"{pill(f.enforcement, ENFORCE_COLOR[f.enforcement])}&nbsp; "
                    f"<b>rule {f.rule}</b> · {f.detail}", unsafe_allow_html=True)

# ---- Data quality ---- #
elif view == "Data quality":
    st.caption("Surfaced, not silently corrected — resolve before the book is treated as clean.")
    items = [("reconciliation", f"{c}: parsed vs stated differ by ${d:,.2f}")
             for c, ok, d in book.recon if not ok]
    items += [("data flag", f"{q.name}: {fl}") for q in book.positions for fl in q.flags]
    if not items:
        st.success("No data-quality issues detected.")
    for kind, detail in items:
        st.markdown(f"{pill('review', '#c78a2a')}&nbsp; <b>{kind}</b> · {detail}",
                    unsafe_allow_html=True)

# ---- Ask the book ---- #
elif view == "Ask the book":
    st.caption("Answers computed by the deterministic tools — every figure shows its source."
               + ("" if DEMO_MODE else
                  " Optionally let the grounded AI model phrase them (falls back if no API key)."))
    use_ai = False if DEMO_MODE else st.toggle("Use grounded AI phrasing")
    q = st.text_input("Ask about the book",
                      placeholder="e.g. How much is unhedged? Which holdings breach my mandate?")
    st.caption("Try: What's my net worth? · How much is unhedged? · "
               "Which holdings breach my mandate? · How much is illiquid? · Any data issues?")
    if q:
        ans = ask_ai(book, q) if use_ai else ask(book, q)
        st.markdown(f"**{ans.summary}**")
        for label, value, src in ans.facts:
            st.markdown(f"- **{label}:** {value}  \n  <span class='prov'>{src}</span>",
                        unsafe_allow_html=True)
