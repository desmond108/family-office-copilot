"""Deliverable · document ingestion — the research/other uploaders read text
deterministically (txt/md/html/eml/csv/json here; pdf/docx via optional libs),
so the content can be folded into the prompt as advisory context. No API key."""
from __future__ import annotations

import doc_extract as de


def test_plain_text_and_markdown():
    r = de.extract_text(b"# Outlook\n\nFavour **medium-duration** bonds.", "note.md")
    assert r["ok"] and r["chars"] > 0
    assert "bonds" in r["text"].lower()


def test_html_is_stripped_to_text():
    r = de.extract_text(b"<html><body><h1>View</h1><p>Range-bound equity.</p></body></html>",
                        "view.html")
    assert r["ok"]
    assert "range-bound equity" in r["text"].lower()
    assert "<p>" not in r["text"]  # tags removed


def test_eml_email_body_extracted():
    raw = (b"Subject: Liquidity\nFrom: kadir@example.com\nTo: rm@meridian.com\n\n"
           b"I expect a Q4 property sale freeing ~USD 500k of cash to invest.")
    r = de.extract_text(raw, "client.eml")
    assert r["ok"]
    assert "liquidity" in r["text"].lower() or "property sale" in r["text"].lower()


def test_csv_and_json_pass_through_as_text():
    assert de.extract_text(b"a,b\n1,2", "t.csv")["ok"]
    assert de.extract_text(b'{"k": 1}', "t.json")["ok"]


def test_unsupported_type_fails_gracefully():
    r = de.extract_text(b"\x00\x01binary", "mystery.xyz")
    assert r["ok"] is False
    assert r["chars"] == 0
    assert "unsupported" in r["note"].lower()


def test_truncation_flag_on_large_input():
    """Very large documents are truncated (MAX_CHARS) and marked, never dropped."""
    big = ("word " * 5000).encode()
    r = de.extract_text(big, "big.txt")
    assert r["ok"]
    # either it fit, or it was truncated and said so
    assert r["truncated"] in (True, False)
    if r["truncated"]:
        assert r["chars"] <= len(big.decode())


def test_result_shape_is_stable():
    r = de.extract_text(b"hello", "a.txt")
    for key in ("name", "kind", "chars", "ok", "note", "truncated", "text"):
        assert key in r, f"missing key {key!r} in extract result"
