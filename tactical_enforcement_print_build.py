"""enforcement_page_build.py — the enforcement-tier mapping as a one-page SVG,
in TWO looks (color = Meridian navy/gold; BW = black line-art), so it can be
merged with the matching flowchart page into the combined v3 handout.

Run: python3 enforcement_page_build.py
  -> tactical_enforcement_print.svg (color) + tactical_enforcement_print_BW.svg
"""
from __future__ import annotations
import html

W, H = 1200, 760

COLOR = {
    "paper": "#ffffff", "ink": "#16203c", "ink_soft": "#47517a", "ink_faint": "#838cad",
    "outer": "#c8cddd", "title_fill": "#131d3d", "title_text": "#eef1fb", "title_border": "none",
    "card_border": "#dfe2ee", "row_border": "#e6e8f0",
    "enf": "#2f6f57", "mon": "#b0872a", "adv": "#6a739a",
    "hdr_fill": "#131d3d", "hdr_text": "#eef1fb",
    "guard_fill": "#131d3d", "guard_lab": "#d0a24a", "guard_text": "#eef1fb",
    "eyebrow": "#8a8f9f",
}
MONO = {
    "paper": "#ffffff", "ink": "#000000", "ink_soft": "#1a1a1a", "ink_faint": "#555555",
    "outer": "#333333", "title_fill": "#ffffff", "title_text": "#000000", "title_border": "#000000",
    "card_border": "#000000", "row_border": "#cccccc",
    "enf": "#000000", "mon": "#000000", "adv": "#000000",
    "hdr_fill": "#000000", "hdr_text": "#ffffff",
    "guard_fill": "#000000", "guard_lab": "#ffffff", "guard_text": "#ffffff",
    "eyebrow": "#333333",
}

P: dict = COLOR
svg: list[str] = []
def add(s): svg.append(s)
def esc(t): return html.escape(str(t), quote=True)


def tier_color(t: str) -> str:
    if t.startswith("ENFORCED"):
        return P["enf"]
    if t.startswith("MONITORED"):
        return P["mon"]
    return P["adv"]


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


def lines_text(x, y, lines, size, color, weight="400", lh=1.28, mono=False):
    fam = ' font-family="Consolas, monospace"' if mono else ""
    parts = [f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" font-weight="{weight}" '
             f'fill="{color}"{fam}>']
    for i, ln in enumerate(lines):
        dy = 0 if i == 0 else size * lh
        parts.append(f'<tspan x="{x:.0f}" dy="{dy:.1f}">{esc(ln)}</tspan>')
    parts.append("</text>")
    add("".join(parts))


def build(mode: str) -> str:
    global P, svg
    P = COLOR if mode == "color" else MONO
    svg = []
    add(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="Helvetica, Arial, sans-serif">')
    add(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" fill="{P["paper"]}" '
        f'stroke="{P["outer"]}" stroke-width="1"/>')

    tb = f' stroke="{P["title_border"]}" stroke-width="1.4"' if P["title_border"] != "none" else ""
    add(f'<rect x="0.5" y="0.5" width="{W-1}" height="44" fill="{P["title_fill"]}"{tb}/>')
    add(f'<text x="{W/2:.0f}" y="28" text-anchor="middle" font-size="17" font-weight="800" '
        f'fill="{P["title_text"]}">Which client conditions actually bind the numbers?</text>')
    lines_text(40, 70, wrap("A client's tactical instructions vary endlessly, but their SHAPE falls into "
                            "just three handling tiers. The copilot classifies each ask and is honest about "
                            "what it can enforce today — it never pretends an instruction is binding when it "
                            "is only a note.", 150), 13, P["ink_soft"])

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
    cy, ch, cw, gap = 108, 150, 366, 21
    for i, (tier, sub, body, eg) in enumerate(cards):
        x = 40 + i * (cw + gap)
        ac = tier_color(tier)
        add(f'<rect x="{x}" y="{cy}" width="{cw}" height="{ch}" fill="{P["paper"]}" '
            f'stroke="{P["card_border"]}" stroke-width="1.4" rx="7"/>')
        add(f'<rect x="{x}" y="{cy}" width="{cw}" height="4" fill="{ac}"/>')
        add(f'<text x="{x+16}" y="{cy+31}" font-size="15" font-weight="800" fill="{ac}">{esc(tier)}</text>')
        add(f'<text x="{x+16}" y="{cy+50}" font-size="11" font-weight="700" fill="{P["ink_faint"]}" '
            f'letter-spacing="0.5">{esc(sub.upper())}</text>')
        lines_text(x+16, cy+71, wrap(body, 48), 12, P["ink_soft"])
        lines_text(x+16, cy+ch-14, [eg], 11.5, P["ink_faint"], mono=True)

    # ---- mapping table ---- #
    add(f'<text x="40" y="300" font-size="12.5" font-weight="800" fill="{P["eyebrow"]}" '
        f'letter-spacing="1.5">THE CLIENT’S ACTUAL MESSAGE, TIER BY TIER</text>')
    COLS = [("The client’s words", 40), ("Shape", 360), ("Tier today", 510),
            ("What the copilot does", 660)]
    TY = 314
    add(f'<rect x="36" y="{TY}" width="1128" height="30" fill="{P["hdr_fill"]}"/>')
    for name, x in COLS:
        add(f'<text x="{x+8}" y="{TY+20}" font-size="12" font-weight="700" '
            f'fill="{P["hdr_text"]}">{esc(name)}</text>')

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
        add(f'<rect x="36" y="{y}" width="1128" height="{rh}" fill="{P["paper"]}" '
            f'stroke="{P["row_border"]}" stroke-width="1"/>')
        ty0 = y + 20
        lines_text(48, ty0, wl, 12, P["ink"], weight="700")
        lines_text(368, ty0, wrap(shape, 22), 11.5, P["ink_soft"])
        add(f'<text x="518" y="{ty0}" font-size="11.5" font-weight="800" '
            f'fill="{tier_color(tier)}">{esc(tier)}</text>')
        lines_text(668, ty0, dl, 11.5, P["ink_soft"])
        y += rh

    # ---- guardrail band ---- #
    gy = y + 16
    add(f'<rect x="36" y="{gy}" width="1128" height="64" fill="{P["guard_fill"]}" rx="5"/>')
    add(f'<text x="52" y="{gy+24}" font-size="11.5" font-weight="800" fill="{P["guard_lab"]}" '
        f'letter-spacing="1">THE GUARDRAIL — TIERED, NOT ABSOLUTE</text>')
    lines_text(52, gy+44, wrap("The copilot still never invents a number. An enforced condition can gate "
                               "or flag a trade — using a figure sourced with provenance — but never "
                               "fabricate one. Advisory and monitored items shape the words and the "
                               "watchlist, never the maths.", 140), 11.5, P["guard_text"])
    add("</svg>")
    return "\n".join(svg)


with open("tactical_enforcement_print.svg", "w") as f:
    f.write(build("color"))
with open("tactical_enforcement_print_BW.svg", "w") as f:
    f.write(build("mono"))
print("wrote tactical_enforcement_print.svg (color) + tactical_enforcement_print_BW.svg")
