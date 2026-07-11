"""enforcement_page_build.py — the enforcement-tier mapping as a black-and-white
SVG page (matching tactical_flow_chart_v2_print_BW), so it can be merged with the
flowchart PDF into one printable handout.

Run: python3 enforcement_page_build.py  ->  tactical_enforcement_print_BW.svg
"""
from __future__ import annotations
import html

W, H = 1200, 760
svg: list[str] = []
def add(s): svg.append(s)
def esc(t): return html.escape(str(t), quote=True)


def wrap(text, max_chars):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def lines_text(x, y, lines, size, weight="400", lh=1.28, anchor="start"):
    parts = [f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}" font-size="{size}" '
             f'font-weight="{weight}" fill="#000000">']
    for i, ln in enumerate(lines):
        dy = 0 if i == 0 else size * lh
        parts.append(f'<tspan x="{x:.0f}" dy="{dy:.1f}">{esc(ln)}</tspan>')
    parts.append("</text>")
    add("".join(parts))


add(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
    f'font-family="Helvetica, Arial, sans-serif">')
add(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" fill="#ffffff" stroke="#333333" stroke-width="1"/>')

# title bar
add(f'<rect x="0.5" y="0.5" width="{W-1}" height="44" fill="#ffffff" stroke="#000000" stroke-width="1.4"/>')
add(f'<text x="{W/2:.0f}" y="28" text-anchor="middle" font-size="17" font-weight="800" fill="#000000">'
    f'Which client conditions actually bind the numbers?</text>')
lines_text(40, 70, wrap("A client's tactical instructions vary endlessly, but their SHAPE falls into "
                        "just three handling tiers. The copilot classifies each ask and is honest about "
                        "what it can enforce today — it never pretends an instruction is binding when it "
                        "is only a note.", 150), 13, anchor="start")

# ---- three tier cards ---- #
cards = [
    ("ENFORCED", "Binds a computed number",
     "Checked against real data and allowed to gate a trade — a target weight (via Apply), "
     "or an absolute price level on a priceable instrument.", "e.g.  “buy gold below $4,000/oz”"),
    ("MONITORED", "Watched, not yet binding",
     "On the watchlist and flagged when hit, but can't gate the math yet — typically a "
     "relative move that needs a defined reference point.", "e.g.  “add after a 15–20% pullback”"),
    ("ADVISORY", "Shapes the write-up only",
     "Folds into the narrative and deck notes — execution style, selection, questions, "
     "research context. Never touches a figure.", "e.g.  “buy in tranches”, “low fees”"),
]
cy, ch = 108, 150
cw, gap = 366, 21
for i, (tier, sub, body, eg) in enumerate(cards):
    x = 40 + i * (cw + gap)
    add(f'<rect x="{x}" y="{cy}" width="{cw}" height="{ch}" fill="#ffffff" stroke="#000000" stroke-width="1.4" rx="6"/>')
    add(f'<rect x="{x}" y="{cy}" width="{cw}" height="4" fill="#000000"/>')
    add(f'<text x="{x+16}" y="{cy+30}" font-size="15" font-weight="800" fill="#000000">{esc(tier)}</text>')
    add(f'<text x="{x+16}" y="{cy+49}" font-size="11" font-weight="700" fill="#333333" '
        f'letter-spacing="0.5">{esc(sub.upper())}</text>')
    lines_text(x+16, cy+70, wrap(body, 48), 12)
    add(f'<text x="{x+16}" y="{cy+ch-14}" font-size="11.5" font-family="Consolas, monospace" '
        f'fill="#333333">{esc(eg)}</text>')

# ---- mapping table ---- #
add(f'<text x="40" y="300" font-size="12.5" font-weight="800" fill="#000000" '
    f'letter-spacing="1.5">THE CLIENT’S ACTUAL MESSAGE, TIER BY TIER</text>')
COLS = [("The client’s words", 40, 320), ("Shape", 360, 150),
        ("Tier today", 510, 150), ("What the copilot does", 660, 500)]
TY = 314
add(f'<rect x="36" y="{TY}" width="1128" height="30" fill="#000000"/>')
for name, x, w in COLS:
    add(f'<text x="{x+8}" y="{TY+20}" font-size="12" font-weight="700" fill="#ffffff">{esc(name)}</text>')

rows = [
    ("MMF 10% · Gold 20% · Bond 20% · Nasdaq 20% · S&P 30%", "allocation target",
     "ENFORCED (Apply)", "Flows through Apply → the numeric targets; drives drift & the rebalance."),
    ("“buy gold below $4,000/oz”", "absolute price trigger", "ENFORCED",
     "Checks live gold vs $4,000 → gates the commodity buy (buy above the level → HOLD), with provenance."),
    ("“add after a 15–20% pullback”", "relative price trigger", "MONITORED",
     "Watchlisted and flagged when hit — does not gate a trade yet (needs a trailing-high reference)."),
    ("“buy the bond fund in tranches”", "execution style", "ADVISORY",
     "Annotates the fixed-income buy row (“execute in tranches”); prints in guidance."),
    ("“low fees, good liquidity”", "selection screen", "ADVISORY",
     "Narrative guidance only — would need an instrument fee/liquidity dataset to bind."),
    ("“concerned about rate hikes”", "macro intent", "ADVISORY",
     "Shapes the CIO commentary tone — a viewpoint, never a figure."),
]
y = TY + 30
for words, shape, tier, does in rows:
    wl = wrap(words, 46)
    dl = wrap(does, 74)
    rh = max(len(wl), len(dl), 1) * 16 + 22
    add(f'<rect x="36" y="{y}" width="1128" height="{rh}" fill="#ffffff" stroke="#cccccc" stroke-width="1"/>')
    ty0 = y + 20
    lines_text(48, ty0, wl, 12, weight="700")
    lines_text(368, ty0, wrap(shape, 22), 11.5, weight="400")
    add(f'<text x="518" y="{ty0}" font-size="11.5" font-weight="800" fill="#000000">{esc(tier)}</text>')
    lines_text(668, ty0, dl, 11.5, weight="400")
    y += rh

# ---- guardrail line ---- #
gy = y + 16
add(f'<rect x="36" y="{gy}" width="1128" height="64" fill="#000000" rx="5"/>')
add(f'<text x="52" y="{gy+24}" font-size="11.5" font-weight="800" fill="#ffffff" '
    f'letter-spacing="1">THE GUARDRAIL — TIERED, NOT ABSOLUTE</text>')
lines_text(52, gy+44, wrap("The copilot still never invents a number. An enforced condition can gate or "
                           "flag a trade — using a figure sourced with provenance — but never fabricate "
                           "one. Advisory and monitored items shape the words and the watchlist, never the maths.",
                           140), 11.5)
# recolor the guardrail text to white (override): re-emit as white by wrapping in a group is complex;
# instead the line above is black on black — fix by drawing white text explicitly:
svg.pop()  # remove the black guardrail body we just added
parts = wrap("The copilot still never invents a number. An enforced condition can gate or flag a trade "
             "— using a figure sourced with provenance — but never fabricate one. Advisory and "
             "monitored items shape the words and the watchlist, never the maths.", 140)
p = [f'<text x="52" y="{gy+44}" font-size="11.5" font-weight="400" fill="#ffffff">']
for i, ln in enumerate(parts):
    dy = 0 if i == 0 else 11.5 * 1.28
    p.append(f'<tspan x="52" dy="{dy:.1f}">{esc(ln)}</tspan>')
p.append("</text>")
add("".join(p))

add("</svg>")
with open("tactical_enforcement_print_BW.svg", "w") as f:
    f.write("\n".join(svg))
print(f"wrote tactical_enforcement_print_BW.svg (table bottom y={y}, guardrail y={gy})")
