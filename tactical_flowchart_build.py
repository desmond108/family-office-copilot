"""tactical_flowchart_build.py — a BPMN-style connected swimlane flowchart of the
tactical-instructions process (the classic Start → process/decision → Finish form
the user attached), as a COMPLEMENT to the matrix-style tactical_swimlane.

Emits a standalone SVG (for render verification) and a self-contained HTML artifact
(tactical_flowchart_note.html) in the Meridian navy/gold house style, theme-aware.

Run:  python3 tactical_flowchart_build.py
"""
from __future__ import annotations
import html

W, H = 1200, 660
GX = 66                       # left lane-label gutter
TITLE_H = 40
PH_Y, PH_H = 40, 38           # phase header band
TOP = PH_Y + PH_H             # 78
LANE_H = (H - TOP) / 3        # 194

# phase x-boundaries
PX = [66, 246, 676, 966, 1200]
PHASES = ["Capture", "Classify & confirm", "Analyse", "Review & generate"]
LANES = [("Client", "Source"), ("Analyst", "You"), ("Copilot", "System")]
LANE_CY = [TOP + LANE_H * (i + 0.5) for i in range(3)]   # 175, 369, 563

svg: list[str] = []
def add(s): svg.append(s)


def esc(t): return html.escape(t, quote=True)


def multiline(cx, cy, lines, size, color, weight="600", cls=""):
    """Centered multi-line text via tspans."""
    n = len(lines)
    y0 = cy - (n - 1) * (size * 0.58)
    parts = [f'<text x="{cx:.0f}" y="{y0:.1f}" text-anchor="middle" '
             f'font-size="{size}" font-weight="{weight}" fill="{color}" '
             f'class="{cls}" style="paint-order:stroke;stroke:var(--paper);'
             f'stroke-width:0;">']
    for i, ln in enumerate(lines):
        dy = 0 if i == 0 else size * 1.16
        parts.append(f'<tspan x="{cx:.0f}" dy="{dy:.1f}">{esc(ln)}</tspan>')
    parts.append('</text>')
    add("".join(parts))


def rect(cx, cy, lines, kind="proc"):
    w, h = 132, 50
    x, y = cx - w / 2, cy - h / 2
    fill = {"proc": "var(--paper)", "bot": "var(--paper)"}[kind]
    stroke = {"proc": "var(--gold-br)", "bot": "var(--line-strong)"}[kind]
    dash = ' stroke-dasharray="5 4"' if kind == "bot" else ""
    sw = 1.6 if kind == "proc" else 1.3
    add(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" rx="7" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash}/>')
    tcol = "var(--ink)" if kind == "proc" else "var(--ink-soft)"
    multiline(cx, cy, lines, 12, tcol, "700")


def term(cx, cy, lines, kind="start"):
    w, h = 128, 46
    x, y = cx - w / 2, cy - h / 2
    fill = "var(--navy-deep)"
    add(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" rx="23" '
        f'fill="{fill}" stroke="var(--gold-br)" stroke-width="1.6"/>')
    multiline(cx, cy, lines, 12, "#eef1fb", "700")


def diamond(cx, cy, lines):
    hw, hh = 66, 36
    pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
    add(f'<polygon points="{pts}" fill="var(--amber-tint)" '
        f'stroke="var(--amber)" stroke-width="1.7"/>')
    multiline(cx, cy, lines, 11.5, "var(--amber-strong)", "800")


def tag(cx, cy, text):
    w, h = 104, 32
    x, y = cx - w / 2, cy - h / 2
    add(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" rx="16" '
        f'fill="var(--amber-tint)" stroke="var(--amber)" stroke-width="1.4"/>')
    multiline(cx, cy, [text], 11, "var(--amber-strong)", "800")


def arrow(path, faint=False):
    marker = "url(#af)" if faint else "url(#a)"
    col = "var(--ink-faint)" if faint else "var(--ink-soft)"
    dash = ' stroke-dasharray="5 4"' if faint else ""
    add(f'<path d="{path}" fill="none" stroke="{col}" stroke-width="1.6" '
        f'marker-end="{marker}"{dash}/>')


def alabel(x, y, text, faint=False):
    col = "var(--ink-faint)" if faint else "var(--ink-soft)"
    st = "italic" if faint else "normal"
    w = len(text) * 5.7 + 8            # background plate so the label clears any line
    add(f'<rect x="{x-w/2:.1f}" y="{y-11:.0f}" width="{w:.0f}" height="15" rx="3" '
        f'fill="var(--paper)" opacity="0.92"/>')
    add(f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="middle" font-size="10.5" '
        f'font-style="{st}" font-weight="600" fill="{col}">{esc(text)}</text>')


# ---------- frame: title, phase headers, lanes ---------- #
add(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
    f'font-family="var(--sans)" class="flow">')
add('<defs>'
    '<marker id="a" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
    '<path d="M0,0 L7,3 L0,6 Z" fill="var(--ink-soft)"/></marker>'
    '<marker id="af" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
    '<path d="M0,0 L7,3 L0,6 Z" fill="var(--ink-faint)"/></marker>'
    '</defs>')

# outer + title
add(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" fill="var(--paper)" '
    f'stroke="var(--line-strong)" stroke-width="1"/>')
add(f'<rect x="0.5" y="0.5" width="{W-1}" height="{TITLE_H}" fill="var(--navy-deep)"/>')
add(f'<text x="{W/2:.0f}" y="{TITLE_H/2+5:.0f}" text-anchor="middle" font-size="16" '
    f'font-weight="800" fill="#eef1fb" letter-spacing="0.3">The tactical-instructions process — end to end</text>')

# phase header band + labels + dashed dividers
add(f'<rect x="{GX}" y="{PH_Y}" width="{W-GX}" height="{PH_H}" fill="var(--slate-tint)" '
    f'stroke="var(--line)" stroke-width="1"/>')
for i, name in enumerate(PHASES):
    cx = (PX[i] + PX[i+1]) / 2
    add(f'<text x="{cx:.0f}" y="{PH_Y+PH_H/2+4:.0f}" text-anchor="middle" font-size="12.5" '
        f'font-weight="700" font-style="italic" fill="var(--navy)">{esc(name)}</text>')
for xb in PX[1:-1]:
    add(f'<line x1="{xb}" y1="{PH_Y}" x2="{xb}" y2="{H}" stroke="var(--line-strong)" '
        f'stroke-width="1.3" stroke-dasharray="3 5"/>')

# lane bands + rotated labels
lane_fill = ["var(--client-tint)", "var(--gold-lane)", "var(--slate-tint)"]
lane_lab = ["var(--navy)", "var(--gold)", "var(--ink-soft)"]
for i, (name, sub) in enumerate(LANES):
    y = TOP + i * LANE_H
    add(f'<rect x="{GX}" y="{y:.0f}" width="{W-GX}" height="{LANE_H:.0f}" '
        f'fill="{lane_fill[i]}" stroke="var(--line)" stroke-width="1"/>')
    add(f'<rect x="0.5" y="{y:.0f}" width="{GX-0.5}" height="{LANE_H:.0f}" '
        f'fill="var(--paper)" stroke="var(--line)" stroke-width="1"/>')
    cy = y + LANE_H / 2
    add(f'<text x="26" y="{cy:.0f}" text-anchor="middle" font-size="13" font-weight="800" '
        f'fill="{lane_lab[i]}" transform="rotate(-90 26 {cy:.0f})">{esc(name)}</text>')
    add(f'<text x="44" y="{cy:.0f}" text-anchor="middle" font-size="9" font-weight="600" '
        f'letter-spacing="1" fill="var(--ink-faint)" transform="rotate(-90 44 {cy:.0f})">{esc(sub.upper())}</text>')

# ---------- nodes ---------- #
term(156, 175, ["Client gives", "instructions"])            # START
rect(430, 175, ["Ask the client", "(clarify)"], "proc")     # CL1
rect(821, 175, ["Hands over", "statements"], "proc")        # CL2

rect(156, 369, ["Paste →", "Sort into items"])              # A1
rect(316, 369, ["Review the", "sorted list"])               # A2
diamond(468, 369, ["Needs", "clarification?"])              # D1
rect(610, 369, ["Confirm", "items"])                        # A3
rect(821, 369, ["Set policy →", "Analyse"])                 # A4
rect(1083, 369, ["Review &", "generate deck"])              # A5

rect(316, 563, ["Classify +", "tag tier  🔒 📡 📝"], "bot") # B1
rect(610, 563, ["Watchlist, guidance", "+ proposed alloc"], "bot")  # B2
rect(746, 563, ["Parse book;", "compute drift"], "bot")     # B3
diamond(892, 563, ["🔒 trigger", "met?"])                    # D2
term(1083, 520, ["Proposal deck", "(PPTX / PDF)"])          # FINISH
tag(1010, 610, "buy → HOLD")                                 # HOLD

# ---------- arrows ---------- #
arrow("M156,198 V344")                                       # START→A1
arrow("M156,394 V563 H250"); alabel(200, 556, "sort")        # A1→B1
arrow("M316,538 V394"); alabel(348, 468, "tiered")           # B1→A2
arrow("M382,369 H404")                                       # A2→D1
arrow("M468,333 V198"); alabel(505, 250, "yes · unclear")    # D1→CL1 (straight up)
arrow("M396,198 V300 H316 V344"); alabel(342, 296, "resolve")    # CL1→A2 loop
arrow("M532,369 H544"); alabel(538, 345, "no")               # D1→A3
arrow("M610,394 V538"); alabel(656, 466, "on confirm")       # A3→B2
arrow("M676,369 H755"); alabel(715, 356, "then")             # A3→A4
arrow("M821,198 V344"); alabel(866, 275, "statements")       # CL2→A4
arrow("M821,394 V520 H746 V538"); alabel(800, 468, "analyse")    # A4→B3
arrow("M812,563 H828")                                       # B3→D2
arrow("M892,527 V369 H1017"); alabel(958, 356, "met · buy stands")  # D2→A5
arrow("M892,599 V610 H958"); alabel(918, 588, "breached")    # D2→HOLD
arrow("M1010,594 V520 H1019")                                # HOLD→FINISH
arrow("M1083,394 V497"); alabel(1120, 455, "generate")       # A5→FINISH
arrow("M610,588 V636 H1083 V543", faint=True); alabel(850, 630, "guidance folds into the deck", faint=True)  # B2→FINISH

add("</svg>")
SVG = "\n".join(svg)

# ---------- standalone SVG (verification) ---------- #
TOKENS_LIGHT = """
  --paper:#ffffff; --ink:#16203c; --ink-soft:#47517a; --ink-faint:#838cad;
  --navy:#1e2a56; --navy-deep:#131d3d; --gold:#9c7422; --gold-br:#b0872a;
  --gold-lane:#fbf6e9; --amber:#b06a17; --amber-strong:#8a4f11; --amber-tint:#fbe6d2;
  --line:#dfe2ee; --line-strong:#c8cddd; --slate-tint:#eef0f6; --client-tint:#eef2fb;
  --sans:system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"""
TOKENS_DARK = """
  --paper:#0f1830; --ink:#e8ebf6; --ink-soft:#aab3d1; --ink-faint:#7883a6;
  --navy:#dbe2f6; --navy-deep:#0a1430; --gold:#d3a94f; --gold-br:#d3a94f;
  --gold-lane:#171f০f; --amber:#e0954a; --amber-strong:#e9a860; --amber-tint:#2c1c0c;
  --line:#22305a; --line-strong:#33477b; --slate-tint:#14203f; --client-tint:#141d3a;""".replace("০f", "0f")

# literal light-palette map so the standalone SVG renders in soffice (no CSS vars)
LIT = {
    "--paper": "#ffffff", "--ink": "#16203c", "--ink-soft": "#47517a", "--ink-faint": "#838cad",
    "--navy": "#1e2a56", "--navy-deep": "#131d3d", "--gold": "#9c7422", "--gold-br": "#b0872a",
    "--gold-lane": "#fbf6e9", "--amber": "#b06a17", "--amber-strong": "#8a4f11",
    "--amber-tint": "#fbe6d2", "--line": "#dfe2ee", "--line-strong": "#c8cddd",
    "--slate-tint": "#eef0f6", "--client-tint": "#eef2fb",
    "--sans": "Helvetica, Arial, sans-serif",
}
flat = SVG.replace('xmlns="http://www.w3.org/2000/svg" ',
                   'xmlns="http://www.w3.org/2000/svg" ')
for k, v in LIT.items():
    flat = flat.replace(f"var({k})", v)
with open("tactical_flowchart.svg", "w") as f:
    f.write(flat)

# ---------- HTML artifact ---------- #
HTML = f"""<style>
  :root {{{TOKENS_LIGHT}
    --ground:#eef0f6; --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;
    --mono:ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace; }}
  @media (prefers-color-scheme: dark) {{ :root {{{TOKENS_DARK} --ground:#05091a; }} }}
  :root[data-theme="light"] {{{TOKENS_LIGHT} --ground:#eef0f6; }}
  :root[data-theme="dark"] {{{TOKENS_DARK} --ground:#05091a; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--ground); color:var(--ink); font-family:var(--sans); line-height:1.5; -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:1240px; margin:0 auto; padding:clamp(18px,4vw,44px) clamp(14px,3vw,30px); }}
  .eyebrow {{ font-size:11.5px; letter-spacing:.18em; text-transform:uppercase; font-weight:700; color:var(--gold-br); margin:0 0 10px; }}
  h1 {{ font-family:var(--serif); font-weight:600; color:var(--navy); font-size:clamp(24px,4.4vw,34px); line-height:1.12; letter-spacing:-.01em; margin:0 0 10px; text-wrap:balance; }}
  .dek {{ font-size:clamp(15px,2.2vw,17px); color:var(--ink-soft); margin:0 0 20px; max-width:70ch; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:9px 20px; margin:0 0 18px; font-size:12.5px; color:var(--ink-soft); }}
  .legend span {{ display:inline-flex; align-items:center; gap:8px; }}
  .k {{ width:26px; height:15px; border-radius:4px; border:1.6px solid var(--gold-br); background:var(--paper); flex:none; }}
  .k.dec {{ width:16px; height:16px; border-radius:3px; transform:rotate(45deg); border-color:var(--amber); background:var(--amber-tint); }}
  .k.term {{ border-radius:8px; background:var(--navy-deep); border-color:var(--gold-br); }}
  .k.bot {{ border-style:dashed; border-color:var(--line-strong); }}
  .scroll {{ overflow-x:auto; border:1px solid var(--line); border-radius:12px; background:var(--paper); box-shadow:0 1px 2px rgba(10,18,40,.05),0 18px 46px -30px rgba(10,18,40,.3); }}
  .flow {{ display:block; width:100%; min-width:1000px; height:auto; }}
  .foot {{ margin-top:20px; font-size:12.5px; color:var(--ink-faint); }}
  .foot b {{ color:var(--ink-soft); }}
  @media print {{ body{{background:#fff;}} .scroll{{overflow:visible;}} .flow{{min-width:0;}} }}
</style>

<div class="wrap">
  <p class="eyebrow">Meridian Family Office Copilot · v8</p>
  <h1>Tactical instructions — process flowchart</h1>
  <p class="dek">The same workflow as the swimlane matrix, drawn as a <b>connected flow</b>: it traces the decision path — the <b>needs-clarification</b> loop back to the client, and the 🔒 <b>enforced-trigger</b> check that gates a buy. Three lanes (Client / Analyst / Copilot) across four phases.</p>
  <div class="legend">
    <span><span class="k term"></span> Start / end</span>
    <span><span class="k"></span> Analyst / client step</span>
    <span><span class="k bot"></span> Copilot (automatic)</span>
    <span><span class="k dec"></span> Decision</span>
  </div>
  <div class="scroll">
    {SVG}
  </div>
  <p class="foot"><b>Read with:</b> the swimlane matrix (who does what, in which phase) answers “my role at a glance”; this flowchart answers “what’s the decision path.” <b>v8:</b> the 🔒 decision gates a rebalance buy against a sourced live price — it can hold a trade, never invent one. · Confidential.</p>
</div>
"""
with open("tactical_flowchart_note.html", "w") as f:
    f.write(HTML)
print("wrote tactical_flowchart.svg + tactical_flowchart_note.html")
