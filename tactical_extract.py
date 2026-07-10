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

ITEM_TYPES = ["entry_trigger", "execution_style", "selection_criteria", "question", "other"]

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
    "4. Cover every instruction; put anything that does not fit the first four "
    "types into type 'other'.\n\n"
    "The item types:\n"
    "  entry_trigger    — a conditional rule keyed to a price or valuation level "
    "(e.g. 'buy below $4,000', 'add after a 15-20% pullback'). Monitorable.\n"
    "  execution_style  — HOW to build the position: lump sum, tranches / "
    "dollar-cost-averaging, initial-then-wait, on-trigger.\n"
    "  selection_criteria — preferences for choosing the actual product "
    "(low fees, high liquidity, quality, physical replication, duration…).\n"
    "  question         — an open question to answer, not an instruction to encode.\n"
    "  other            — anything else worth keeping as context.\n\n"
    "Return ONLY a JSON object (no prose, no markdown fences) with this shape:\n"
    "{\n"
    '  "items": [\n'
    "    {\n"
    '      "type": one of ' + ", ".join(ITEM_TYPES) + ",\n"
    '      "instrument": string|null,   // sleeve / instrument it applies to, if named\n'
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
        out.append({
            "type": t,
            "instrument": (it.get("instrument") or None),
            "action": (it.get("action") or None),
            "threshold": (it.get("threshold") or None),
            "detail": detail,
            "verbatim": (it.get("verbatim") or detail).strip(),
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
    low = phrase.lower()
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
