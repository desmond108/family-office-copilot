"""portfolio_qa.py — conversational Q&A over the consolidated book.

The agentic layer, built on the same discipline as everything else: the
DETERMINISTIC tools compute every number (from the parsed statements + provenance);
the LLM only (a) interprets the question and (b) phrases the answer using ONLY the
facts the tools returned. It cannot invent or recompute a figure — the numbers are
never in its hands.

Two modes:
  - ask()    — rule-based routing + templated answer. No network, no billing, the
               source of truth. Always works.
  - ask_ai() — hands the deterministic 'briefing' (every fact + its provenance) to
               Claude, which answers arbitrary phrasings grounded strictly in it.
               Optional; falls back to ask() when no key / offline.

Run:  python3 portfolio_qa.py            (deterministic demo, offline)
      python3 portfolio_qa.py --ai       (also show Claude-narrated answers; needs network)
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field

from datafeed import resolve_key
from statement_parser import (FX, FX_SOURCE, STMT_DIR, TODAY, parse_custodian_a,
                              parse_custodian_b, parse_custodian_c, reconcile, to_holdings)
from suitability_check import Bands, RiskProfile, suitability_check

CLAUDE_MODEL = "claude-haiku-4-5-20251001"


# --------------------------------------------------------------------------- #
# The book (deterministic snapshot)
# --------------------------------------------------------------------------- #

@dataclass
class Book:
    positions: list
    liabilities: list
    gross: float
    debt: float
    net: float
    suit: list
    recon: list           # (custodian, ok, delta)
    as_of: str
    prov: str             # base provenance string


def load_book() -> Book:
    sts = [reconcile(parse_custodian_a(STMT_DIR / "custodianA_uob.csv")),
           reconcile(parse_custodian_b(STMT_DIR / "custodianB_eurobank.csv")),
           reconcile(parse_custodian_c(STMT_DIR / "custodianC_familyoffice.json"))]
    positions = [p for st in sts for p in st.positions]
    gross = sum(p.mv_base for p in positions)
    debt = sum(abs(lb["balance"]) for st in sts for lb in st.liabilities)
    liabilities = [lb for st in sts for lb in st.liabilities]
    profile = RiskProfile(
        mandate="advisory",
        allocation_bands={"equity": Bands(0.30, 0.65), "fixed_income": Bands(0.10, 0.40),
                          "commodity": Bands(0.00, 0.25), "cash": Bands(0.05, 0.90)},
        min_liquid_pct=0.10)
    suit = suitability_check(profile, to_holdings(sts), as_of=TODAY)
    recon = [(st.custodian, st.recon_ok, st.recon_delta) for st in sts]
    return Book(positions, liabilities, round(gross, 2), round(debt, 2),
                round(gross - debt, 2), suit, recon, sts[0].as_of,
                f"parsed from {len(sts)} custodian statements (as of {sts[0].as_of}); "
                f"non-USD converted via {FX_SOURCE}")


# --------------------------------------------------------------------------- #
# Answer type
# --------------------------------------------------------------------------- #

@dataclass
class Answer:
    summary: str
    facts: list = field(default_factory=list)   # (label, value, source)
    tool: str = ""

    def render(self) -> str:
        lines = [f"  {self.summary}"]
        for label, value, src in self.facts:
            lines.append(f"     · {label}: {value}   [{src}]")
        return "\n".join(lines)


def _usd(x: float) -> str:
    return f"${x:,.0f}"


# --------------------------------------------------------------------------- #
# Deterministic tools — every number comes from here
# --------------------------------------------------------------------------- #

CLASS_SYNONYMS = {
    "equity": ["equity", "equities", "stock", "shares"],
    "fixed_income": ["fixed income", "bond", "bonds", "fixed-income", "credit"],
    "commodity": ["commodity", "gold", "commodities"],
    "cash": ["cash", "money market", "liquidity reserve"],
    "alternatives": ["alternative", "alternatives", "private equity", "pe fund"],
    "real_estate": ["real estate", "property", "real-estate"],
}


def t_totals(book: Book, _q="") -> Answer:
    lev = book.debt / book.net if book.net else 0
    return Answer(
        f"Net worth is {_usd(book.net)} — {_usd(book.gross)} of assets less "
        f"{_usd(book.debt)} of borrowing (leverage {lev:.1%}).",
        [("gross assets", _usd(book.gross), book.prov),
         ("liabilities", _usd(book.debt), "Lombard loan, Alpine Trust statement"),
         ("net worth", _usd(book.net), "gross − liabilities"),
         ("leverage", f"{lev:.1%}", "debt ÷ net worth")], "totals")


def t_by_class(book: Book, cls: str) -> Answer:
    total = sum(p.mv_base for p in book.positions if p.asset_class == cls)
    pct = total / book.gross if book.gross else 0
    names = [p.name for p in book.positions if p.asset_class == cls]
    label = cls.replace("_", " ")
    if not names:
        return Answer(f"There is no {label} exposure in the book.", tool="by_class")
    return Answer(
        f"{label.capitalize()} exposure is {_usd(total)} — {pct:.1%} of gross assets, "
        f"across {len(names)} holding(s).",
        [(f"{label} value", _usd(total), book.prov),
         ("% of gross", f"{pct:.1%}", "computed"),
         ("holdings", ", ".join(names), "custodian statements")], "by_class")


def t_by_currency(book: Book, _q="") -> Answer:
    by = {}
    for p in book.positions:
        by[p.currency] = by.get(p.currency, 0.0) + p.mv_base
    unhedged = sum(v for c, v in by.items() if c != "USD")
    parts = ", ".join(f"{c} {v/book.gross:.1%}" for c, v in sorted(by.items(), key=lambda x: -x[1]))
    return Answer(
        f"By currency of exposure: {parts}. Unhedged non-USD exposure is "
        f"{_usd(unhedged)} ({unhedged/book.gross:.1%} of gross).",
        [("currency mix", parts, book.prov),
         ("unhedged non-USD", f"{_usd(unhedged)} ({unhedged/book.gross:.1%})",
          f"FX via {FX_SOURCE}")], "by_currency")


def t_by_custodian(book: Book, name: str = "") -> Answer:
    by = {}
    for p in book.positions:
        by.setdefault(p.custodian, []).append(p)
    if name:
        match = [c for c in by if name.lower() in c.lower()]
        by = {c: by[c] for c in match} or by
    facts, lines = [], []
    for cust, ps in by.items():
        tot = sum(p.mv_base for p in ps)
        lines.append(f"{cust} {_usd(tot)}")
        facts.append((cust, f"{_usd(tot)} · {len(ps)} holdings", f"{cust} statement"))
    return Answer("Holdings by custodian: " + "; ".join(lines) + ".", facts, "by_custodian")


def t_suitability(book: Book, _q="") -> Answer:
    breaches = [f for f in book.suit if f.enforcement in ("block", "flag")]
    if not breaches:
        return Answer("The book is within all defined suitability bands.", tool="suitability")
    facts = [(f.enforcement, f.detail, "suitability engine") for f in breaches]
    return Answer(
        f"{len(breaches)} suitability issue(s) need attention (worst action: "
        f"{max(f.enforcement for f in breaches)}).", facts, "suitability")


def t_concentration(book: Book, _q="") -> Answer:
    top = sorted(book.positions, key=lambda p: -p.mv_base)[:3]
    facts = [(p.name, f"{_usd(p.mv_base)} ({p.mv_base/book.gross:.1%})", f"{p.custodian} statement")
             for p in top]
    big = top[0]
    return Answer(
        f"Largest position is {big.name} at {_usd(big.mv_base)} "
        f"({big.mv_base/book.gross:.1%} of gross). Top three shown.", facts, "concentration")


def t_rate_scenario(book: Book, _q="") -> Answer:
    fi = [p for p in book.positions if p.asset_class == "fixed_income"]
    total = sum(p.mv_base for p in fi)
    # Honest: precise sensitivity needs each bond's effective duration, which is
    # NOT sourced for these specific instruments — do not estimate it.
    facts = [(p.name, _usd(p.mv_base), "duration NOT sourced for this bond → [SOURCE REQUIRED]")
             for p in fi]
    return Answer(
        f"Fixed-income exposure is {_usd(total)} across {len(fi)} bond(s). A precise "
        f"+100bp impact needs each bond's effective duration, which is not sourced for "
        f"these specific instruments — I won't estimate it. (For fund holdings like "
        f"VCIT/BND the durations ARE sourced, so their impact can be computed.)",
        facts, "rate_scenario")


def t_data_quality(book: Book, _q="") -> Answer:
    facts = []
    for cust, ok, delta in book.recon:
        if not ok:
            facts.append(("reconciliation", f"{cust}: Δ ${delta:,.2f}", "parsed vs stated total"))
    for p in book.positions:
        for fl in p.flags:
            facts.append(("data flag", f"{p.name}: {fl}", f"{p.custodian} statement"))
    if not facts:
        return Answer("No data-quality issues detected.", tool="data_quality")
    return Answer(f"{len(facts)} data-quality item(s) to resolve before the book is treated as clean.",
                  facts, "data_quality")


def t_liquidity(book: Book, _q="") -> Answer:
    illiquid_cls = {"alternatives", "real_estate"}
    liquid = sum(p.mv_base for p in book.positions if p.asset_class not in illiquid_cls)
    illiquid = book.gross - liquid
    return Answer(
        f"Liquid holdings are {_usd(liquid)} ({liquid/book.gross:.1%} of gross); "
        f"illiquid (alternatives + real estate) are {_usd(illiquid)} ({illiquid/book.gross:.1%}).",
        [("liquid", f"{_usd(liquid)} ({liquid/book.gross:.1%})", book.prov),
         ("illiquid", f"{_usd(illiquid)} ({illiquid/book.gross:.1%})", "alternatives + real estate")],
        "liquidity")


# --------------------------------------------------------------------------- #
# Rule-based router
# --------------------------------------------------------------------------- #

def route(q: str):
    ql = q.lower()
    # 1. asset-class exposure (a class word + a context word)
    for cls, syns in CLASS_SYNONYMS.items():
        if any(s in ql for s in syns) and any(w in ql for w in
                ("expos", "how much", "holding", "have", "allocation", "weight", " in ")):
            return lambda b: t_by_class(b, cls)
    # 2. specific intents (before the generic totals catch)
    if any(w in ql for w in ("currency", "fx", " eur", " chf", "unhedged", "dollar")):
        return t_by_currency
    if any(w in ql for w in ("custodian", "uob", "banque", "alpine", "by bank", "which bank", "hold at")):
        name = next((n for n in ("uob", "banque", "alpine") if n in ql), "")
        return lambda b: t_by_custodian(b, name)
    if any(w in ql for w in ("suitab", "breach", "mandate", "complian", "band", "unsuitab")):
        return t_suitability
    if any(w in ql for w in ("concentrat", "largest", "biggest", "top position", "single")):
        return t_concentration
    if any(w in ql for w in ("rate", "duration", "interest", "+100", "100bp", "hike")):
        return t_rate_scenario
    if any(w in ql for w in ("stale", "unresolved", "data qual", "reconcil", "clean", "issue")):
        return t_data_quality
    if any(w in ql for w in ("liquid", "illiquid")):
        return t_liquidity
    # 3. totals (net worth / leverage)
    if any(w in ql for w in ("net worth", "total", "leverage", "debt", "borrow", "worth")):
        return t_totals
    # 4. class-only fallback, then default
    for cls, syns in CLASS_SYNONYMS.items():
        if any(s in ql for s in syns):
            return lambda b: t_by_class(b, cls)
    return t_totals


def ask(book: Book, question: str) -> Answer:
    return route(question)(book)


# --------------------------------------------------------------------------- #
# Grounded Claude mode (optional) — LLM phrases the answer, never the numbers
# --------------------------------------------------------------------------- #

def briefing(book: Book) -> dict:
    """Every fact the LLM is allowed to use, each with provenance. Pre-computed
    so the model never has to do arithmetic — only look up and phrase."""
    by_class, by_ccy = {}, {}
    for p in book.positions:
        by_class[p.asset_class] = round(by_class.get(p.asset_class, 0.0) + p.mv_base, 2)
        by_ccy[p.currency] = round(by_ccy.get(p.currency, 0.0) + p.mv_base, 2)
    return {
        "as_of": book.as_of, "provenance": book.prov,
        "gross_assets_usd": book.gross, "liabilities_usd": book.debt,
        "net_worth_usd": book.net, "leverage_pct": round(book.debt / book.net * 100, 1),
        "exposure_by_asset_class_usd": by_class,
        "exposure_by_currency_usd": by_ccy,
        "pct_of_gross": {k: round(v / book.gross * 100, 1) for k, v in by_class.items()},
        "holdings": [{"name": p.name, "asset_class": p.asset_class, "custodian": p.custodian,
                      "currency": p.currency, "value_usd": p.mv_base,
                      "flags": p.flags} for p in book.positions],
        "suitability": [f"[{f.enforcement}] {f.detail}" for f in book.suit],
        "reconciliation": [{"custodian": c, "ties_out": ok, "delta_usd": d} for c, ok, d in book.recon],
        "note": "Bond effective durations are NOT in this briefing for the two held bonds; "
                "do not estimate rate sensitivity for them.",
    }


_SYS = ("You are a family-office portfolio assistant. Answer the question in 1–3 sentences "
        "using ONLY the JSON FACTS provided. Never invent, add, or recompute a number — quote "
        "figures exactly as given. If the facts don't answer it, say precisely what data is "
        "missing. Be concise and professional; do not give investment advice.")


def ask_ai(book: Book, question: str, api_key: str | None = None, llm=None) -> Answer:
    """Grounded LLM answer. Falls back to deterministic ask() if unavailable."""
    key = api_key or resolve_key("ANTHROPIC_API_KEY") or resolve_key("API_KEY_260627")
    facts = briefing(book)
    prompt = f"FACTS (JSON):\n{json.dumps(facts)}\n\nQUESTION: {question}"
    try:
        if llm is not None:
            text = llm(_SYS, prompt)
        else:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            msg = client.messages.create(model=CLAUDE_MODEL, max_tokens=300,
                                         system=_SYS, messages=[{"role": "user", "content": prompt}])
            text = msg.content[0].text.strip()
        return Answer(text, [("source", "grounded in the deterministic briefing", book.prov)], "claude")
    except Exception as e:  # noqa: BLE001 — degrade to deterministic
        det = ask(book, question)
        det.summary = f"[Claude unavailable: {type(e).__name__}; deterministic answer] " + det.summary
        return det


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #

QUESTIONS = [
    "What's my net worth and how much leverage am I running?",
    "How much equity exposure do I have?",
    "What's my gold / commodity exposure?",
    "Break down my holdings by currency — how much is unhedged?",
    "What do I hold at Banque Privée?",
    "Which holdings breach my mandate?",
    "What's my single largest position?",
    "What happens to my bonds if rates rise 1%?",
    "Are there any data-quality or reconciliation issues?",
    "How much of the book is illiquid?",
]

if __name__ == "__main__":
    use_ai = "--ai" in sys.argv
    book = load_book()
    print("=" * 92)
    print(f"PORTFOLIO Q&A  ·  net worth {_usd(book.net)}  ·  {book.prov}")
    print("Numbers come from the deterministic tools; the LLM (if used) only phrases them.")
    print("=" * 92)
    for q in QUESTIONS:
        print(f"\nQ: {q}")
        print(ask(book, q).render())
        if use_ai:
            ai = ask_ai(book, q)
            print(f"  ⟢ AI: {ai.summary}")
