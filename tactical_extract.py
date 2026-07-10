"""tactical_extract.py — v6 free-text tactical instructions -> typed items.

The problem this solves: a client's ad-hoc guidance ("buy the bond fund in
tranches", "only add Nasdaq after a 15-20% pullback", "gold below USD 4,000/oz",
"low fees and good liquidity", "what's the impact of rate hikes?") is *varied*
but not *unstructured* — it clusters into four recognisable TYPES, each wanting
different downstream handling. A single free-text box flattens all four into
narrated prose; this module classifies the text into typed slots the engine can
act on, while anything that doesn't classify stays as free-text guidance.

The four types:
  * entry_trigger   — a conditional, monitorable rule (price / valuation level).
                      Feeds a monitoring watchlist (cf. the sibling repo's
                      alerts.py). e.g. "buy gold below $4,000/oz".
  * execution_style — how to build a position: lump sum / tranches (DCA) /
                      initial-then-wait / on-trigger. e.g. "buy in tranches".
  * selection_criteria — screening preferences on the products chosen.
                      e.g. "low fees, good liquidity, good quality".
  * question        — an open question to answer, not an instruction to encode.
                      e.g. "what's the impact of rate-hike expectations?".
  * other           — anything that doesn't classify; kept as free-text guidance.

DISCIPLINE (identical to vision_extract): the LLM only CLASSIFIES and copies the
client's own words / levels — it never invents a threshold, a level, or a number
that the client did not state (threshold is null when unstated). A human reviews
and edits every item before it drives anything. Unlike a scanned statement, the
input here is already text, so a deterministic keyword classifier
(`heuristic_extract`) gives a usable first pass with NO API key — the keyless /
DEMO build still demonstrates the whole extract -> review -> confirm flow.
"""
from __future__ import annotations

import json
import re

TACTICAL_MODEL = "claude-opus-4-8"

ITEM_TYPES = ["allocation_target", "entry_trigger", "execution_style", "selection_criteria",
              "question", "needs_clarification", "other"]

# The six allocation sleeves the app can pre-fill from an allocation_target item
# (must match app.ALLOC_KEYS). Any allocation_target the client states is mapped to
# one of these, aggregated, and PROPOSED to the analyst — never auto-applied.
SLEEVES = ["equity", "fixed_income", "commodity", "cash", "fx", "structured_products"]

INSTRUCTIONS = (
    "You are a private-banking portfolio analyst. You are given a client's or "
    "analyst's FREE-TEXT tactical instructions about how to invest a portfolio. "
    "Split the text into distinct instructions and CLASSIFY each one into a typed "
    "item. Do not merge two different asks into one item — e.g. 'buy in tranches, "
    "but what about rate hikes?' is an execution_style item AND a question.\n\n"
    "ABSOLUTE RULES:\n"
    "1. Classify and copy the client's own words only. Do NOT invent, compute, or "
    "add a threshold, price level, or percentage the client did not state. If a "
    "level is not stated, use null for `threshold`.\n"
    "2. Preserve every level exactly as written ('15%-20%', 'USD 4,000/oz').\n"
    "3. `verbatim` must quote the source phrase the item came from.\n"
    "4. Cover every instruction. If it is CLEAR but doesn't fit the first four "
    "types, use 'other'. If it is ambiguous, self-contradictory, missing a level it "
    "seems to require, or you genuinely cannot understand it, use "
    "'needs_clarification' and put the SPECIFIC question / what is unclear in "
    "`detail` — do NOT guess its meaning or silently file it under 'other'.\n\n"
    "The item types:\n"
    "  allocation_target — a TARGET PORTFOLIO WEIGHT for an asset class / sleeve "
    "(e.g. '20% in gold', 'allocate 30% to the S&P 500', 'money market fund: 10%'). "
    "Set `weight_pct` to the number and map it to one `asset_class` from this list: "
    + ", ".join(SLEEVES) + " (gold/precious→commodity, S&P/Nasdaq/stocks→equity, "
    "bond/treasury→fixed_income, money-market/cash→cash). A weight to buy AT a "
    "condition (e.g. 'buy 5% once it dips') is an entry_trigger, NOT this.\n"
    "  entry_trigger    — a conditional rule keyed to a price or valuation level "
    "(e.g. 'buy below $4,000', 'add after a 15-20% pullback'). Monitorable.\n"
    "  execution_style  — HOW to build the position: lump sum, tranches / "
    "dollar-cost-averaging, initial-then-wait, on-trigger.\n"
    "  selection_criteria — preferences for choosing the actual product "
    "(low fees, high liquidity, quality, physical replication, duration…).\n"
    "  question         — an open question to answer, not an instruction to encode.\n"
    "  needs_clarification — ambiguous, contradictory, or unintelligible as written; "
    "put the clarifying question in `detail` (e.g. \"'be aggressive but protect "
    "capital' — which takes priority?\").\n"
    "  other            — clear, but doesn't fit the four actionable types above.\n\n"
    "Return ONLY a JSON object (no prose, no markdown fences) with this shape:\n"
    "{\n"
    '  "items": [\n'
    "    {\n"
    '      "type": one of ' + ", ".join(ITEM_TYPES) + ",\n"
    '      "instrument": string|null,   // sleeve / instrument it applies to, if named\n'
    '      "asset_class": string|null,  // allocation_target ONLY: one of the sleeves above\n'
    '      "weight_pct": number|null,   // allocation_target ONLY: the target weight, e.g. 20\n'
    '      "action": string|null,       // e.g. "buy", "buy initial 5%", "park in money market"\n'
    '      "threshold": string|null,    // the stated level, VERBATIM; null if none stated\n'
    '      "detail": string,            // one-line normalised statement of the instruction\n'
    '      "verbatim": string           // the source phrase, quoted\n'
    "    }\n"
    "  ]\n"
    "}"
)


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of the model reply (robust to fences / stray prose)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001 — fall back to the first {...} span
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no JSON object found in the model response")
        return json.loads(text[start:end + 1])


def _clean(items: list) -> list[dict]:
    """Normalise items to the canonical shape and drop empties."""
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        t = it.get("type")
        t = t if t in ITEM_TYPES else "other"
        detail = (it.get("detail") or it.get("verbatim") or "").strip()
        if not detail:
            continue
        ac = it.get("asset_class")
        ac = ac if ac in SLEEVES else None
        wp = it.get("weight_pct")
        try:
            wp = float(wp) if wp is not None and str(wp).strip() != "" else None
        except (TypeError, ValueError):
            wp = None
        out.append({
            "type": t,
            "instrument": (it.get("instrument") or None),
            "asset_class": ac,         # allocation_target only (else None)
            "weight_pct": wp,          # allocation_target only (else None)
            "action": (it.get("action") or None),
            "threshold": (it.get("threshold") or None),
            "detail": detail,
            "verbatim": (it.get("verbatim") or detail).strip(),
            "keep": True,    # analyst review-time fields (default on / empty)
            "note": "",
        })
    return out


def extract(text: str, api_key: str) -> dict:
    """Classify free-text tactical instructions into typed items via the LLM.

    Returns {"items": [...], "source": "llm"}. Raises on refusal / empty / bad
    JSON so the caller can degrade to `heuristic_extract`."""
    text = (text or "").strip()
    if not text:
        return {"items": [], "source": "llm"}

    import anthropic  # lazy — keeps the dep optional for the keyless demo build
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=TACTICAL_MODEL, max_tokens=4000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user",
                   "content": INSTRUCTIONS + "\n\nCLIENT / ANALYST TEXT:\n" + text}],
    )
    if msg.stop_reason == "refusal":
        raise RuntimeError("the model declined to classify this text")
    out = "".join(b.text for b in msg.content if b.type == "text").strip()
    if not out:
        raise RuntimeError("empty response from the classification model")
    data = _extract_json(out)
    return {"items": _clean(data.get("items", [])), "source": "llm"}


# --------------------------------------------------------------------------- #
# Deterministic fallback — no API key needed. A keyword classifier over the
# input sentences. It NEVER fabricates a level: `threshold` is only filled from a
# number/level actually present in the source phrase (regex), else null.
# --------------------------------------------------------------------------- #
_LEVEL_RE = re.compile(
    r"(?:USD|US\$|\$|€|£)\s?[\d,]+(?:\.\d+)?(?:\s?/\s?oz)?"   # $4,000/oz, USD 4,000
    r"|\d+(?:\.\d+)?\s?%(?:\s?[-–]\s?\d+(?:\.\d+)?\s?%)?"      # 15%-20%, 5%
    r"|\d+(?:\.\d+)?\s?[-–]\s?\d+(?:\.\d+)?\s?%",              # 15-20%
    re.IGNORECASE)

_TRIGGER_KW = ("below", "above", "under", "over", "pull back", "pullback",
               "pulls back", "drops", "falls", "correction", "dips", "reaches",
               "recent high", "from its high", "when it", "once", "if ")
_EXEC_KW = ("tranche", "tranches", "dollar-cost", "dollar cost", "dca",
            "average in", "averaging in", "phased", "phase in", "scale in",
            "gradually", "over time", "stagger", "initial", "start with", "leg in")
_CRIT_KW = ("low fee", "low-fee", "low cost", "low-cost", "cheap", "expense ratio",
            "ter", "liquid", "liquidity", "good quality", "high quality", "quality",
            "physical", "replication", "tracking error", "reputable", "large aum",
            "tight spread", "duration", "short duration", "medium duration")
# Conservative cues that an instruction is ambiguous / can't be acted on as written.
# (The LLM path does the real ambiguity detection; this only catches obvious cases.)
_UNCLEAR_KW = ("not sure", "unsure", "maybe", "somehow", "i think", "tbc",
               "to be confirmed", "to be discussed", "figure out", "??", "etc etc")

# Map an instrument name to an allocation sleeve (first match wins; order matters —
# commodity before equity so 'gold' isn't swallowed by a generic term).
_ASSET_MAP = [
    (("money market", "mmf", "t-bill", "treasury bill", "cash", "deposit"), "cash"),
    (("gold", "silver", "precious", "commodit", "oil", "bullion"), "commodity"),
    (("bond", "treasur", "fixed income", "fixed-income", "govt", "government debt",
      "credit", "duration", "aggregate"), "fixed_income"),
    (("s&p", "sp 500", "sp500", "nasdaq", "equit", "stock", "shares", "msci",
      "russell", "dow"), "equity"),
    (("structured", "autocall", "phoenix", "note"), "structured_products"),
    (("fx", "currency", "forex", "eurusd", "hedge the"), "fx"),
]
# Cues that a percentage is a TARGET WEIGHT rather than a conditional/entry level.
_ALLOC_CUE = ("allocate", "allocation", "benchmark", "target", "weight", "long-term",
              "long term", "hold ", "of the portfolio", "of portfolio")
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s?%")


def _asset_of(low: str) -> str | None:
    for names, sleeve in _ASSET_MAP:
        if any(n in low for n in names):
            return sleeve
    return None


def _alloc_from(phrase: str):
    """If the phrase states a target weight for an asset class, return
    (asset_class, weight_pct); else None. Requires an asset, a percentage, and an
    allocation cue (an allocation cue keyword, or a 'name: NN%' colon pattern), and
    NO entry-trigger cue — so 'buy 5% once it dips' stays a trigger."""
    low = phrase.lower().strip()
    if any(k in low for k in _TRIGGER_KW):
        return None
    m = _PCT_RE.search(phrase)
    asset = _asset_of(low)
    if not m or not asset:
        return None
    colon = bool(re.search(r":\s*[^%]*\d+(?:\.\d+)?\s?%", phrase))
    if not colon and not any(c in low for c in _ALLOC_CUE):
        return None
    return asset, float(m.group(1))


def _split(text: str) -> list[str]:
    """Split free text into candidate instructions (sentences / clauses / lines)."""
    parts: list[str] = []
    for line in text.replace("\r", "").split("\n"):
        line = re.sub(r"^\s*(?:\d+[\.\)]|[-*•])\s*", "", line).strip()
        if not line:
            continue
        # split on sentence enders and semicolons, keeping question marks
        parts += [p.strip() for p in re.split(r"(?<=[.?;])\s+|;\s*", line) if p.strip()]
    return parts


def _classify(phrase: str) -> str:
    low = phrase.lower().strip()
    if low in ("?", "??", "...", "") or any(k in low for k in _UNCLEAR_KW):
        return "needs_clarification"
    if phrase.strip().endswith("?") or low.startswith(("what", "how", "why", "will ",
                                                        "should", "is ", "impact of")):
        return "question"
    if any(k in low for k in _EXEC_KW):
        return "execution_style"
    if any(k in low for k in _TRIGGER_KW) and (_LEVEL_RE.search(phrase) or "high" in low):
        return "entry_trigger"
    if any(k in low for k in _CRIT_KW):
        return "selection_criteria"
    if any(k in low for k in _TRIGGER_KW):
        return "entry_trigger"
    return "other"


def heuristic_extract(text: str) -> dict:
    """A no-API keyword classifier. Same shape as `extract` (source="heuristic").
    Used in DEMO_MODE / when no key is present so the flow works keyless."""
    items = []
    for phrase in _split(text or ""):
        alloc = _alloc_from(phrase)
        if alloc:
            asset, pct = alloc
            items.append({"type": "allocation_target", "asset_class": asset,
                          "weight_pct": pct, "instrument": None, "action": None,
                          "threshold": None, "detail": phrase, "verbatim": phrase})
            continue
        t = _classify(phrase)
        m = _LEVEL_RE.search(phrase)
        items.append({
            "type": t,
            "instrument": None,
            "action": None,
            "threshold": m.group(0).strip() if (m and t == "entry_trigger") else None,
            "detail": phrase,
            "verbatim": phrase,
        })
    return {"items": _clean(items), "source": "heuristic"}
