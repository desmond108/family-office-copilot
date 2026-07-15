"""build_pdfs.py — render the Markdown / .eml sample documents to PDF.

Produces PDF versions of the sample research/other documents so the app's PDF
text-extraction path (doc_extract._from_pdf -> pypdf) can be tested too. The PDFs
carry a real, selectable text layer (reportlab), so pypdf extracts them cleanly.

Sources kept alongside; this only adds the .pdf twins. Run:
    python3 sample_documents/build_pdfs.py
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
                                ListFlowable, ListItem)

HERE = Path(__file__).parent

NAVY = HexColor("#1e2a56"); GOLD = HexColor("#b0872a")
INK = HexColor("#16203c"); SOFT = HexColor("#47517a"); LINE = HexColor("#c8cddd")

EYEBROW = ParagraphStyle("eyebrow", fontName="Helvetica-Bold", fontSize=7.5,
                         textColor=GOLD, spaceAfter=10, leading=10)
H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, textColor=NAVY,
                    spaceBefore=2, spaceAfter=8, leading=20)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12.5, textColor=NAVY,
                    spaceBefore=12, spaceAfter=5, leading=15)
H3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=11, textColor=NAVY,
                    spaceBefore=9, spaceAfter=3, leading=13)
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10, textColor=INK,
                      leading=14.5, spaceAfter=6, alignment=TA_LEFT)
ITEM = ParagraphStyle("item", parent=BODY, spaceAfter=3)
NUMITEM = ParagraphStyle("numitem", parent=BODY, spaceAfter=4,
                         leftIndent=16, firstLineIndent=-16)
META = ParagraphStyle("meta", fontName="Helvetica", fontSize=9.5, textColor=SOFT,
                      leading=13, spaceAfter=1)


def inline(text: str) -> str:
    """Escape, then turn **bold** / *italic* / `code` into reportlab markup."""
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', text)
    text = re.sub(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", text)
    return text


def _collect_items(lines: list[str], i: int, pat: re.Pattern) -> tuple[list[str], int]:
    """Collect list items, tolerating wrapped/indented continuations AND blank
    lines between items (as long as the next non-blank line is another item)."""
    items: list[str] = []
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        m = pat.match(s)
        if m:
            items.append(m.group(1).strip()); i += 1; continue
        if not s:                                   # blank — is the list continuing?
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and items and pat.match(lines[j].strip()):
                i = j; continue                     # skip blank(s), keep collecting
            break
        if items and (raw.startswith("  ") or raw.startswith("\t")):
            items[-1] += " " + s; i += 1; continue  # wrapped continuation
        break
    return items, i


BULLET = re.compile(r"[-*]\s+(.*)")
NUMBER = re.compile(r"\d+\.\s+(.*)")


def md_to_flowables(text: str) -> list:
    lines = text.replace("\r", "").split("\n")
    flow: list = []
    para: list[str] = []

    def flush():
        if para:
            flow.append(Paragraph(inline(" ".join(para)), BODY))
            para.clear()

    i = 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        if not s:
            flush(); i += 1; continue
        # setext heading (TEXT then a line of --- or ===)
        if (i + 1 < len(lines) and re.fullmatch(r"[-=]{3,}", lines[i + 1].strip())
                and not BULLET.match(s)):
            flush(); flow.append(Paragraph(inline(s), H2)); i += 2; continue
        # atx headings
        m = re.match(r"(#{1,4})\s+(.*)", s)
        if m:
            flush()
            style = {1: H1, 2: H2, 3: H3}.get(len(m.group(1)), H3)
            flow.append(Paragraph(inline(m.group(2)), style)); i += 1; continue
        # horizontal rule
        if re.fullmatch(r"[-*_]{3,}", s):
            flush(); flow.append(HRFlowable(width="100%", color=LINE, spaceBefore=6,
                                            spaceAfter=8)); i += 1; continue
        # bullet list
        if BULLET.match(s):
            flush()
            items, i = _collect_items(lines, i, BULLET)
            flow.append(ListFlowable([Paragraph(inline(it), ITEM) for it in items],
                                     bulletType="bullet", bulletColor=GOLD, start="•",
                                     leftIndent=14, bulletFontSize=9))
            continue
        # numbered list — number inline (reportlab's auto-increment is unreliable
        # when list items carry custom indents), with a hanging indent.
        if NUMBER.match(s):
            flush()
            items, i = _collect_items(lines, i, NUMBER)
            for n, it in enumerate(items, 1):
                flow.append(Paragraph(f'<font color="#1e2a56"><b>{n}.</b></font>&nbsp; '
                                      + inline(it), NUMITEM))
            continue
        para.append(s); i += 1
    flush()
    return flow


def eml_to_flowables(text: str) -> list:
    """Split RFC822-ish headers from the body; render a header block + the body."""
    parts = text.replace("\r", "").split("\n\n", 1)
    head_txt = parts[0]
    body = parts[1] if len(parts) > 1 else ""
    headers: dict[str, str] = {}
    for ln in head_txt.split("\n"):
        m = re.match(r"([A-Za-z-]+):\s*(.*)", ln)
        if m:
            headers[m.group(1).lower()] = m.group(2).strip()
    flow: list = [Paragraph(inline(headers.get("subject", "(no subject)")), H1)]
    for k in ("from", "to", "date"):
        if headers.get(k):
            flow.append(Paragraph(f"<b>{k.title()}:</b> {inline(headers[k])}", META))
    flow.append(HRFlowable(width="100%", color=LINE, spaceBefore=8, spaceAfter=10))
    flow.extend(md_to_flowables(body))
    return flow


def render(src: Path, flowables: list):
    out = src.with_suffix(".pdf")
    doc = SimpleDocTemplate(str(out), pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=src.stem)
    story = [Paragraph("SAMPLE DOCUMENT · SYNTHETIC — FOR TESTING", EYEBROW),
             HRFlowable(width="100%", color=GOLD, thickness=1.2, spaceAfter=12)]
    story += flowables
    doc.build(story)
    print(f"wrote {out.relative_to(HERE.parent)}")


TARGETS = [
    HERE / "research" / "Meridian_CIO_Market_Outlook_Q3_2026.md",
    HERE / "other" / "Client_Review_Meeting_Notes_260703.md",
    HERE / "other" / "Client_Email_Kadir_260705.eml",
]

if __name__ == "__main__":
    for src in TARGETS:
        text = src.read_text()
        flow = eml_to_flowables(text) if src.suffix == ".eml" else md_to_flowables(text)
        render(src, flow)
