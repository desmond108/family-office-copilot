"""tactical_flow_chart_v2_build.py — BPMN-style connected swimlane flowchart of the
v10 tactical-instructions process (Start -> process -> Finish), a COMPLEMENT to the
matrix-style tactical_swimlane.

v10 flow: the client's tactical text is passed VERBATIM to the AI model together with
the intake parameters, the deterministic FACTS, the holdings + statement source and
the research / other documents, in ONE self-contained prompt — the AI writes the
proposal narrative; the engine still computes every number. (This replaces the v6-v8
Sort -> classify -> confirm -> enforce pipeline that earlier versions of this chart
showed.)

Emits TWO looks, same layout:
  * COLOR  — Meridian navy/gold, theme-aware  -> tactical_flow_chart_v2_note.html (+ .svg)
  * PRINT  — white background, black line-art, no fills, for printing & annotating with
             a pen/pencil on paper      -> tactical_flow_chart_v2_print_BW_note.html (+ .svg)

Run:  python3 tactical_flow_chart_v2_build.py
"""
from __future__ import annotations
import html

W, H = 1200, 660
GX = 66
TITLE_H = 40
PH_Y, PH_H = 40, 38
TOP = PH_Y + PH_H
LANE_H = (H - TOP) / 3

PX = [66, 336, 606, 936, 1200]
PHASES = ["Capture", "Compute · deterministic", "Assemble & generate", "Deliver"]
LANES = [("Client", "Source"), ("Analyst", "You"), ("Copilot", "System")]

# ----- palettes ----------------------------------------------------------- #
COLOR = {
    "paper": "var(--paper)", "ink": "var(--ink)", "ink_soft": "var(--ink-soft)",
    "ink_faint": "var(--ink-faint)",
    "title_fill": "var(--navy-deep)", "title_text": "#eef1fb", "title_border": "none",
    "term_fill": "var(--navy-deep)", "term_stroke": "var(--gold-br)", "term_text": "#eef1fb",
    "proc_stroke": "var(--gold-br)", "proc_text": "var(--ink)", "proc_sw": 1.6,
    "bot_stroke": "var(--line-strong)", "bot_text": "var(--ink-soft)", "bot_sw": 1.3, "bot_dash": True,
    "ai_stroke": "var(--gold-br)", "ai_text": "var(--ink)", "ai_sw": 2.3, "ai_spark": True,
    "lane_fill": ["var(--client-tint)", "var(--gold-lane)", "var(--slate-tint)"],
    "lane_lab": ["var(--navy)", "var(--gold)", "var(--ink-soft)"], "lane_sub": "var(--ink-faint)",
    "phase_band": "var(--slate-tint)", "phase_text": "var(--navy)",
    "line": "var(--line)", "line_strong": "var(--line-strong)",
    "arrow": "var(--ink-soft)", "arrow_faint": "var(--ink-faint)",
    "label": "var(--ink-soft)", "label_faint": "var(--ink-faint)", "plate": "var(--paper)",
}
MONO = {
    "paper": "#ffffff", "ink": "#000000", "ink_soft": "#1a1a1a", "ink_faint": "#555555",
    "title_fill": "#ffffff", "title_text": "#000000", "title_border": "#000000",
    "term_fill": "#ffffff", "term_stroke": "#000000", "term_text": "#000000",
    "proc_stroke": "#000000", "proc_text": "#000000", "proc_sw": 1.5,
    "bot_stroke": "#000000", "bot_text": "#000000", "bot_sw": 1.2, "bot_dash": True,
    "ai_stroke": "#000000", "ai_text": "#000000", "ai_sw": 2.2, "ai_spark": False,
    "lane_fill": ["#ffffff", "#ffffff", "#ffffff"],
    "lane_lab": ["#000000", "#000000", "#000000"], "lane_sub": "#555555",
    "phase_band": "#ffffff", "phase_text": "#000000",
    "line": "#9a9a9a", "line_strong": "#333333",
    "arrow": "#000000", "arrow_faint": "#777777",
    "label": "#000000", "label_faint": "#666666", "plate": "#ffffff",
}

P: dict = COLOR
svg: list[str] = []
def add(s): svg.append(s)
def esc(t): return html.escape(t, quote=True)


def multiline(cx, cy, lines, size, color, weight="600"):
    n = len(lines)
    y0 = cy - (n - 1) * (size * 0.58)
    parts = [f'<text x="{cx:.0f}" y="{y0:.1f}" text-anchor="middle" font-size="{size}" '
             f'font-weight="{weight}" fill="{color}">']
    for i, ln in enumerate(lines):
        dy = 0 if i == 0 else size * 1.16
        parts.append(f'<tspan x="{cx:.0f}" dy="{dy:.1f}">{esc(ln)}</tspan>')
    parts.append('</text>')
    add("".join(parts))


def rect(cx, cy, lines, kind="proc"):
    w, h = 132, 50
    x, y = cx - w / 2, cy - h / 2
    if kind == "proc":
        stroke, sw, dash, tcol = P["proc_stroke"], P["proc_sw"], "", P["proc_text"]
    else:
        stroke, sw, tcol = P["bot_stroke"], P["bot_sw"], P["bot_text"]
        dash = ' stroke-dasharray="5 4"' if P["bot_dash"] else ""
    add(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" rx="7" fill="{P["paper"]}" '
        f'stroke="{stroke}" stroke-width="{sw}"{dash}/>')
    multiline(cx, cy, lines, 12, tcol, "700")


def term(cx, cy, lines):
    w, h = 128, 46
    x, y = cx - w / 2, cy - h / 2
    add(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" rx="23" fill="{P["term_fill"]}" '
        f'stroke="{P["term_stroke"]}" stroke-width="1.6"/>')
    multiline(cx, cy, lines, 12, P["term_text"], "700")


def aimodel(cx, cy, lines):
    """The AI-model node — a distinct, accented rounded box (the one place a model
    writes prose). Model-agnostic: labelled 'AI Model', never a specific vendor."""
    w, h = 152, 54
    x, y = cx - w / 2, cy - h / 2
    add(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" rx="11" fill="{P["paper"]}" '
        f'stroke="{P["ai_stroke"]}" stroke-width="{P["ai_sw"]}"/>')
    disp = list(lines)
    if P["ai_spark"]:
        disp[0] = "✨ " + disp[0]
    multiline(cx, cy, disp, 12, P["ai_text"], "800")


def arrow(path, faint=False):
    col = P["arrow_faint"] if faint else P["arrow"]
    marker = "url(#af)" if faint else "url(#a)"
    dash = ' stroke-dasharray="5 4"' if faint else ""
    add(f'<path d="{path}" fill="none" stroke="{col}" stroke-width="1.6" '
        f'marker-end="{marker}"{dash}/>')


def alabel(x, y, text, faint=False):
    col = P["label_faint"] if faint else P["label"]
    st = "italic" if faint else "normal"
    w = len(text) * 5.7 + 8
    add(f'<rect x="{x-w/2:.1f}" y="{y-11:.0f}" width="{w:.0f}" height="15" rx="3" '
        f'fill="{P["plate"]}" opacity="0.92"/>')
    add(f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="middle" font-size="10.5" '
        f'font-style="{st}" font-weight="600" fill="{col}">{esc(text)}</text>')


def build(mode: str) -> str:
    global P, svg
    P = COLOR if mode == "color" else MONO
    svg = []
    add(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="var(--sans)" class="flow">')
    add('<defs>'
        f'<marker id="a" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
        f'<path d="M0,0 L7,3 L0,6 Z" fill="{P["arrow"]}"/></marker>'
        f'<marker id="af" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
        f'<path d="M0,0 L7,3 L0,6 Z" fill="{P["arrow_faint"]}"/></marker>'
        '</defs>')
    # frame
    add(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" fill="{P["paper"]}" '
        f'stroke="{P["line_strong"]}" stroke-width="1"/>')
    tb = f' stroke="{P["title_border"]}" stroke-width="1.4"' if P["title_border"] != "none" else ""
    add(f'<rect x="0.5" y="0.5" width="{W-1}" height="{TITLE_H}" fill="{P["title_fill"]}"{tb}/>')
    add(f'<text x="{W/2:.0f}" y="{TITLE_H/2+5:.0f}" text-anchor="middle" font-size="16" '
        f'font-weight="800" fill="{P["title_text"]}" letter-spacing="0.3">'
        f'The tactical-instructions process — end to end (v10)</text>')
    # phase band
    add(f'<rect x="{GX}" y="{PH_Y}" width="{W-GX}" height="{PH_H}" fill="{P["phase_band"]}" '
        f'stroke="{P["line"]}" stroke-width="1"/>')
    for i, name in enumerate(PHASES):
        cx = (PX[i] + PX[i+1]) / 2
        add(f'<text x="{cx:.0f}" y="{PH_Y+PH_H/2+4:.0f}" text-anchor="middle" font-size="12.5" '
            f'font-weight="700" font-style="italic" fill="{P["phase_text"]}">{esc(name)}</text>')
    # lanes
    for i, (name, sub) in enumerate(LANES):
        y = TOP + i * LANE_H
        add(f'<rect x="{GX}" y="{y:.0f}" width="{W-GX}" height="{LANE_H:.0f}" '
            f'fill="{P["lane_fill"][i]}" stroke="{P["line"]}" stroke-width="1"/>')
        add(f'<rect x="0.5" y="{y:.0f}" width="{GX-0.5}" height="{LANE_H:.0f}" '
            f'fill="{P["paper"]}" stroke="{P["line"]}" stroke-width="1"/>')
        cy = y + LANE_H / 2
        add(f'<text x="26" y="{cy:.0f}" text-anchor="middle" font-size="13" font-weight="800" '
            f'fill="{P["lane_lab"][i]}" transform="rotate(-90 26 {cy:.0f})">{esc(name)}</text>')
        add(f'<text x="44" y="{cy:.0f}" text-anchor="middle" font-size="9" font-weight="600" '
            f'letter-spacing="1" fill="{P["lane_sub"]}" transform="rotate(-90 44 {cy:.0f})">'
            f'{esc(sub.upper())}</text>')

    # phase dividers — drawn AFTER the lane fills so the dashed lines run the full
    # height (top to bottom), then the nodes are drawn on top of them.
    for xb in PX[1:-1]:
        add(f'<line x1="{xb}" y1="{PH_Y}" x2="{xb}" y2="{H-1}" stroke="{P["line_strong"]}" '
            f'stroke-width="1.4" stroke-dasharray="4 5"/>')

    # lane y-centres: Client 175 · Analyst 369 · Copilot 563
    # ----- nodes ----- #
    # Client
    term(201, 175, ["Client gives", "instructions + docs"])
    # Analyst
    rect(201, 369, ["Paste tactical text", "+ upload documents"])
    rect(471, 369, ["Set policy &", "parameters → Analyse"])
    rect(771, 369, ["Review the", "assembled prompt"])
    rect(1068, 369, ["Review & download", "the deck"])
    # Copilot
    rect(471, 563, ["Parse book; compute", "deterministic FACTS"], "bot")
    rect(700, 563, ["Assemble one", "self-contained prompt"], "bot")
    aimodel(900, 563, ["AI Model writes", "the narrative"])
    term(1068, 563, ["Proposal deck", "(PPTX / PDF)"])

    # ----- arrows ----- #
    arrow("M201,198 V344")                                    # client -> paste
    arrow("M267,369 H405"); alabel(336, 356, "then")         # paste -> set policy
    arrow("M471,394 V538"); alabel(507, 466, "Analyse")      # set policy -> compute
    arrow("M537,563 H634"); alabel(586, 550, "then")         # compute -> assemble
    arrow("M700,538 V440 H771 V394"); alabel(742, 436, "review")   # assemble -> review prompt
    arrow("M837,369 H870 V536"); alabel(902, 452, "Generate")      # review prompt (right) -> AI model
    arrow("M976,563 H1004")                                   # AI model -> deck
    arrow("M1068,540 V394"); alabel(1104, 466, "download")   # deck -> review & download

    # external-model + guardrail annotations (faint)
    arrow("M771,344 V302", faint=True)
    alabel(771, 294, "or copy → any AI model", faint=True)
    alabel(724, 636, "Every figure is computed deterministically — the AI writes prose only, never a number.", faint=True)
    add("</svg>")
    return "\n".join(svg)


# ----- token maps for standalone SVG / HTML -------------------------------- #
TOK_LIGHT = ("--paper:#ffffff;--ink:#16203c;--ink-soft:#47517a;--ink-faint:#838cad;"
             "--navy:#1e2a56;--navy-deep:#131d3d;--gold:#9c7422;--gold-br:#b0872a;"
             "--gold-lane:#fbf6e9;--amber:#b06a17;--amber-strong:#8a4f11;--amber-tint:#fbe6d2;"
             "--line:#dfe2ee;--line-strong:#c8cddd;--slate-tint:#eef0f6;--client-tint:#eef2fb;"
             "--sans:system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;")
TOK_DARK = ("--paper:#0f1830;--ink:#e8ebf6;--ink-soft:#aab3d1;--ink-faint:#7883a6;"
            "--navy:#dbe2f6;--navy-deep:#0a1430;--gold:#d3a94f;--gold-br:#d3a94f;"
            "--gold-lane:#171f0f;--amber:#e0954a;--amber-strong:#e9a860;--amber-tint:#2c1c0c;"
            "--line:#22305a;--line-strong:#33477b;--slate-tint:#14203f;--client-tint:#141d3a;")
LIT = {"--paper": "#ffffff", "--ink": "#16203c", "--ink-soft": "#47517a", "--ink-faint": "#838cad",
       "--navy": "#1e2a56", "--navy-deep": "#131d3d", "--gold": "#9c7422", "--gold-br": "#b0872a",
       "--gold-lane": "#fbf6e9", "--amber": "#b06a17", "--amber-strong": "#8a4f11",
       "--amber-tint": "#fbe6d2", "--line": "#dfe2ee", "--line-strong": "#c8cddd",
       "--slate-tint": "#eef0f6", "--client-tint": "#eef2fb", "--sans": "Helvetica, Arial, sans-serif"}


def literalize(s):
    for k, v in LIT.items():
        s = s.replace(f"var({k})", v)
    return s


SVG_COLOR = build("color")
SVG_PRINT = build("print").replace('font-family="var(--sans)"',
                                   'font-family="Helvetica, Arial, sans-serif"')

# standalone SVGs (for render verification)
with open("tactical_flow_chart_v2_v10.svg", "w") as f:
    f.write(literalize(SVG_COLOR))
with open("tactical_flow_chart_v2_print_BW_v10.svg", "w") as f:
    f.write(SVG_PRINT)

# ----- HTML artifacts ------------------------------------------------------ #
SERIF = '"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif'

HTML_COLOR = f"""<style>
  :root {{ {TOK_LIGHT} --ground:#eef0f6; --serif:{SERIF};
    --mono:ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace; }}
  @media (prefers-color-scheme: dark) {{ :root {{ {TOK_DARK} --ground:#05091a; }} }}
  :root[data-theme="light"] {{ {TOK_LIGHT} --ground:#eef0f6; }}
  :root[data-theme="dark"] {{ {TOK_DARK} --ground:#05091a; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--ground); color:var(--ink); font-family:var(--sans); line-height:1.5; -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:1240px; margin:0 auto; padding:clamp(18px,4vw,44px) clamp(14px,3vw,30px); }}
  .eyebrow {{ font-size:11.5px; letter-spacing:.18em; text-transform:uppercase; font-weight:700; color:var(--gold-br); margin:0 0 10px; }}
  h1 {{ font-family:var(--serif); font-weight:600; color:var(--navy); font-size:clamp(24px,4.4vw,34px); line-height:1.12; letter-spacing:-.01em; margin:0 0 10px; text-wrap:balance; }}
  .dek {{ font-size:clamp(15px,2.2vw,17px); color:var(--ink-soft); margin:0 0 20px; max-width:70ch; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:9px 20px; margin:0 0 18px; font-size:12.5px; color:var(--ink-soft); }}
  .legend span {{ display:inline-flex; align-items:center; gap:8px; }}
  .k {{ width:26px; height:15px; border-radius:4px; border:1.6px solid var(--gold-br); background:var(--paper); flex:none; }}
  .k.term {{ border-radius:8px; background:var(--navy-deep); border-color:var(--gold-br); }}
  .k.bot {{ border-style:dashed; border-color:var(--line-strong); }}
  .k.ai {{ border-width:2.3px; border-radius:6px; }}
  .scroll {{ overflow-x:auto; border:1px solid var(--line); border-radius:12px; background:var(--paper); box-shadow:0 1px 2px rgba(10,18,40,.05),0 18px 46px -30px rgba(10,18,40,.3); }}
  .flow {{ display:block; width:100%; min-width:1000px; height:auto; }}
  .foot {{ margin-top:20px; font-size:12.5px; color:var(--ink-faint); }}
  .foot b {{ color:var(--ink-soft); }}
  @media print {{ body{{background:#fff;}} .scroll{{overflow:visible;}} .flow{{min-width:0;}} }}
</style>

<div class="wrap">
  <p class="eyebrow">Meridian Family Office Copilot · v10</p>
  <h1>Tactical instructions — process flowchart</h1>
  <p class="dek">The v10 flow, drawn as a <b>connected path</b>: the client's tactical text is passed <b>verbatim</b> to the <b>AI Model</b> — together with the intake parameters, the deterministic FACTS, the holdings and the documents — in <b>one self-contained prompt</b> the analyst can review, generate from, or copy into <b>any AI model</b>. The engine still computes every number. Three lanes (Client / Analyst / Copilot) across four phases.</p>
  <div class="legend">
    <span><span class="k term"></span> Start / end</span>
    <span><span class="k"></span> Analyst / client step</span>
    <span><span class="k bot"></span> Copilot (automatic)</span>
    <span><span class="k ai"></span> AI Model (writes prose)</span>
  </div>
  <div class="scroll">{SVG_COLOR}</div>
  <p class="foot"><b>Read with:</b> the swimlane matrix answers “my role at a glance”; this flowchart answers “what’s the path.” A <b>white / print</b> version (for pen-and-paper annotation) is the companion document. · Confidential.</p>
</div>
"""

HTML_PRINT = f"""<style>
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:#ffffff; color:#000000; font-family:Helvetica,Arial,sans-serif; line-height:1.5; }}
  .wrap {{ max-width:1240px; margin:0 auto; padding:28px 22px; }}
  .eyebrow {{ font-size:11.5px; letter-spacing:.18em; text-transform:uppercase; font-weight:700; color:#000; margin:0 0 8px; }}
  h1 {{ font-weight:700; color:#000; font-size:clamp(22px,4vw,30px); line-height:1.14; margin:0 0 8px; }}
  .dek {{ font-size:14.5px; color:#222; margin:0 0 8px; max-width:74ch; }}
  .hint {{ font-size:12.5px; color:#333; margin:0 0 16px; border-left:3px solid #000; padding-left:12px; }}
  .scroll {{ overflow-x:auto; border:1.4px solid #000; border-radius:6px; background:#fff; }}
  .flow {{ display:block; width:100%; min-width:1000px; height:auto; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:8px 20px; margin:0 0 16px; font-size:12.5px; color:#000; }}
  .legend span {{ display:inline-flex; align-items:center; gap:8px; }}
  .k {{ width:26px; height:15px; border:1.5px solid #000; background:#fff; flex:none; border-radius:4px; }}
  .k.term {{ border-radius:8px; }}
  .k.bot {{ border-style:dashed; }}
  .k.ai {{ border-width:2.2px; border-radius:6px; }}
  .foot {{ margin-top:16px; font-size:12px; color:#444; }}
  @media print {{ .scroll{{overflow:visible; border:none;}} .flow{{min-width:0;}} .hint{{display:none;}} }}
</style>

<div class="wrap">
  <p class="eyebrow">Meridian Family Office Copilot · v10 — worksheet</p>
  <h1>Tactical instructions — process flowchart (print &amp; annotate · B&amp;W)</h1>
  <p class="dek">White line-art of the v10 flow. Print it and mark it up by hand — trace a client's path from their words to the deck, and note where the prompt is reviewed or copied into another AI model.</p>
  <p class="hint">Tip: <b>File → Print</b> (landscape, “fit to page”, background graphics off) gives a clean A4/Letter sheet. Nothing is filled in, so pen and pencil read clearly.</p>
  <div class="legend">
    <span><span class="k term"></span> Start / end</span>
    <span><span class="k"></span> Analyst / client step</span>
    <span><span class="k bot"></span> Copilot (automatic)</span>
    <span><span class="k ai"></span> AI Model (writes prose)</span>
  </div>
  <div class="scroll">{SVG_PRINT}</div>
  <p class="foot">The AI Model writes the narrative only; every figure is computed deterministically by the engine and is unchanged by the model. · Confidential.</p>
</div>
"""

with open("tactical_flow_chart_v2_note_v10.html", "w") as f:
    f.write(HTML_COLOR)
with open("tactical_flow_chart_v2_print_BW_note_v10.html", "w") as f:
    f.write(HTML_PRINT)
print("wrote color + print .svg and _note.html")
