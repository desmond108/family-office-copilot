"""vision_extract.py — v5 LLM/vision statement ingestion (PDF / image -> structured).

This is the ONE place in the pipeline that reads an UNSTRUCTURED document. A
vision-capable model (claude-opus-4-8) TRANSCRIBES the holdings printed on a
custodian statement into a canonical JSON schema. It does NOT compute, convert,
or invent anything: it copies the printed figures verbatim (names, currencies,
printed market values, ISINs). The deterministic layer downstream
(`statement_parser.parse_extracted` + `reconcile`) does ALL the maths — FX
conversion to the USD base, house-code resolution, and the reconciliation
checksum that catches a misread against the statement's own printed total. So
the never-invent-a-number discipline holds: the model only reads numbers that
are printed on the page, every derived figure is deterministic, and the analyst
reviews/corrects the transcription before the engine runs.

Needs an API key (real vision call) — the app gates this behind DEMO_MODE and a
present key, and guides keyless/demo users to the CSV/JSON path instead. The
`anthropic` import is lazy so the keyless build never imports it.
"""
from __future__ import annotations

import base64
import json
import re

EXTRACT_MODEL = "claude-opus-4-8"

# The asset classes the deterministic engine understands. The model must map each
# holding to one of these (same list as app.ALLOC_KEYS + the illiquid sleeves).
ASSET_CLASSES = [
    "equity", "fixed_income", "commodity", "cash",
    "alternatives", "real_estate", "fx", "structured_products",
]

_MEDIA = {
    "pdf": ("application/pdf", "document"),
    "png": ("image/png", "image"),
    "jpg": ("image/jpeg", "image"),
    "jpeg": ("image/jpeg", "image"),
    "webp": ("image/webp", "image"),
    "gif": ("image/gif", "image"),
}

INSTRUCTIONS = (
    "You are a meticulous private-banking operations analyst. You are given a "
    "client's bank / custodian statement as a PDF or image. TRANSCRIBE the "
    "holdings it shows into structured JSON.\n\n"
    "ABSOLUTE RULES:\n"
    "1. Transcribe ONLY what is printed. Do NOT compute, convert, re-round, "
    "estimate, or invent any number — copy printed values exactly as shown.\n"
    "2. Do NOT convert currencies. Record each position's market value in its OWN "
    "printed currency (a separate deterministic step does the FX conversion).\n"
    "3. If a field is not printed on the statement, use null. Never guess.\n"
    "4. Include every holding / line item you can read.\n"
    "5. Map each holding to the closest asset_class from this exact list: "
    + ", ".join(ASSET_CLASSES) + ".\n\n"
    "Return ONLY a JSON object (no prose, no markdown fences) with this shape:\n"
    "{\n"
    '  "custodian": string|null,            // bank / custodian name as printed\n'
    '  "entity": string|null,               // account holder / entity label if shown\n'
    '  "account_class": string|null,        // e.g. "custody", "trust" if shown\n'
    '  "base_currency": string,             // statement reporting currency, e.g. "USD"\n'
    '  "as_of": string|null,                // statement date, ISO YYYY-MM-DD if determinable\n'
    '  "stated_total_usd": number|null,     // the statement\'s own printed total portfolio value (in base_currency)\n'
    '  "positions": [\n'
    "    {\n"
    '      "name": string,                  // instrument name as printed\n'
    '      "asset_class": string,           // one of the allowed list above\n'
    '      "instrument_type": string|null,  // e.g. "equity_etf","govt_bond","money_market","cash","hedge_fund"\n'
    '      "identifier": string|null,       // ISIN / ticker / code as printed\n'
    '      "id_type": "ISIN"|"CCY"|"HOUSE"|null,\n'
    '      "currency": string,              // the position\'s own currency\n'
    '      "market_value_ccy": number,      // printed market value IN THAT CURRENCY\n'
    '      "val_as_of": string|null\n'
    "    }\n"
    "  ],\n"
    '  "liabilities": [ {"type": string, "balance": number, "rate": number|null} ]\n'
    "}"
)


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of the model's reply (robust to stray prose/fences)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001 — fall back to first {...} span
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no JSON object found in the model response")
        return json.loads(text[start:end + 1])


def extract(file_bytes: bytes, filename: str, api_key: str) -> dict:
    """Transcribe a PDF/image statement into the canonical extraction dict.

    Returns the parsed JSON dict (see INSTRUCTIONS for the shape). Raises on an
    unsupported file type, a model refusal, an empty reply, or unparseable JSON —
    the caller degrades to a clear error message."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _MEDIA:
        raise ValueError(f"unsupported file type '.{ext}' — expected PDF or an image")
    media_type, block_kind = _MEDIA[ext]
    data = base64.standard_b64encode(file_bytes).decode("ascii")  # no newlines

    import anthropic  # lazy — keeps the dep optional for the keyless demo build
    client = anthropic.Anthropic(api_key=api_key)
    doc_block = {"type": block_kind,
                 "source": {"type": "base64", "media_type": media_type, "data": data}}
    msg = client.messages.create(
        model=EXTRACT_MODEL, max_tokens=16000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": [doc_block, {"type": "text", "text": INSTRUCTIONS}]}],
    )
    if msg.stop_reason == "refusal":
        raise RuntimeError("the model declined to transcribe this document")
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    if not text:
        raise RuntimeError("empty response from the extraction model")
    data = _extract_json(text)
    data.setdefault("positions", [])
    data.setdefault("liabilities", [])
    return data
