"""doc_extract.py — v9: pull PLAIN TEXT out of the Research (2) and Other (3)
documents so their content can inform the copilot as ADVISORY context.

Discipline (identical to the rest of the app): this only TRANSCRIBES what the
document already says — it computes nothing and invents nothing. The extracted
text is fed to the LLM as ANALYST GUIDANCE (intent / context), never as a source
of portfolio figures; every number in the deck still comes from the deterministic
engine. A human sees the extracted text in the Analyst-inputs panel.

Text formats (txt / md / html / rtf / eml / msg / csv / json / log) are decoded
deterministically with NO API key, so this works in the keyless demo build. PDF
and DOCX use pure-python libraries (pypdf / python-docx) imported lazily; if they
are not installed the doc degrades to "not extracted" (name still recorded) rather
than crashing. Images / legacy .doc are not text-extracted here.
"""
from __future__ import annotations

import re

# Keep any single document's contribution bounded so the prompt stays reasonable.
MAX_CHARS = 6000

_TEXT_EXT = {"txt", "md", "markdown", "text", "log", "csv", "tsv", "json", "eml", "msg"}


def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _clean(text: str) -> str:
    """Collapse runaway whitespace so the excerpt reads cleanly."""
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)          # drop tags
    raw = re.sub(r"&nbsp;", " ", raw)
    raw = re.sub(r"&amp;", "&", raw)
    raw = re.sub(r"&lt;", "<", raw).replace("&gt;", ">")
    return re.sub(r"[ \t]{2,}", " ", raw)


def _strip_rtf(raw: str) -> str:
    raw = re.sub(r"\\'[0-9a-fA-F]{2}", "", raw)      # hex escapes
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", raw)     # control words
    raw = re.sub(r"[{}]", "", raw)                    # groups
    return raw


def _from_pdf(data: bytes) -> tuple[str | None, str]:
    try:
        from pypdf import PdfReader          # pure-python, deploy-safe
        import io
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages]
        text = "\n\n".join(pages).strip()
        if not text:
            return None, "no selectable text (likely a scanned PDF — needs OCR/vision)"
        return text, ""
    except ModuleNotFoundError:
        return None, "PDF text needs the 'pypdf' package (not installed)"
    except Exception as e:  # noqa: BLE001
        return None, f"PDF read error: {type(e).__name__}"


def _from_docx(data: bytes) -> tuple[str | None, str]:
    try:
        import docx                          # python-docx, pure-python
        import io
        d = docx.Document(io.BytesIO(data))
        text = "\n".join(p.text for p in d.paragraphs).strip()
        if not text:
            return None, "no text found in the .docx"
        return text, ""
    except ModuleNotFoundError:
        return None, "DOCX text needs the 'python-docx' package (not installed)"
    except Exception as e:  # noqa: BLE001
        return None, f"DOCX read error: {type(e).__name__}"


def extract_text(data: bytes, filename: str) -> dict:
    """Return {name, kind, text, chars, ok, note, truncated}. `ok` is False (with a
    reason in `note`) when the format can't be text-extracted here — never a guess."""
    ext = _ext(filename)
    text: str | None = None
    note = ""

    if ext in _TEXT_EXT:
        raw = data.decode("utf-8", "replace")
        text = _clean(raw)
    elif ext in ("html", "htm"):
        text = _clean(_strip_html(data.decode("utf-8", "replace")))
    elif ext == "rtf":
        text = _clean(_strip_rtf(data.decode("utf-8", "replace")))
    elif ext == "pdf":
        text, note = _from_pdf(data)
        text = _clean(text) if text else None
    elif ext in ("docx",):
        text, note = _from_docx(data)
        text = _clean(text) if text else None
    elif ext in ("png", "jpg", "jpeg", "gif", "bmp", "tiff"):
        note = "image — not text-extracted (use section 1 vision ingestion for figures)"
    elif ext == "doc":
        note = "legacy .doc not supported — save as .docx / .pdf / .txt"
    else:
        note = f"unsupported type '.{ext}'"

    if not text:
        return {"name": filename, "kind": ext, "text": "", "chars": 0,
                "ok": False, "note": note or "no text extracted", "truncated": False}

    truncated = len(text) > MAX_CHARS
    if truncated:
        text = text[:MAX_CHARS].rstrip() + " …"
    return {"name": filename, "kind": ext, "text": text, "chars": len(text),
            "ok": True, "note": ("truncated for length" if truncated else ""),
            "truncated": truncated}
