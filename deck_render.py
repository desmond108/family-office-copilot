"""deck_render.py — shared provenance-first HTML rendering for the deck family.

Every value renders through datum(), which shows the figure + its citation, or an
amber SOURCE REQUIRED / stale / reported-date-unknown marker. Same visual system
as the proposal deck so the review reads as the same product.
"""
from __future__ import annotations

import html

from datafeed import Figure


def fmt(fig: Figure) -> str:
    if not fig.ok:
        return "[SOURCE REQUIRED]"
    v = fig.value
    if fig.unit == "%":
        return f"{float(v):.2f}%"
    if fig.unit in ("USD", "USD/oz") and isinstance(v, (int, float)) and abs(v) >= 1000:
        if abs(v) >= 1e9:
            s = f"${v/1e9:,.1f}bn"
        elif abs(v) >= 1e6:
            s = f"${v/1e6:,.2f}m"
        elif fig.unit == "USD/oz":
            s = f"${v:,.2f}"
        else:
            s = f"${v:,.0f}"
        return s + (" /oz" if fig.unit == "USD/oz" else "")
    if fig.unit == "yr":
        return f"{v} yr"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return f"{v:,}" if isinstance(v, int) else str(v)


def datum(fig: Figure) -> str:
    if not fig.ok:
        note = html.escape(fig.note or "no feed available")
        return f'<span class="req">SOURCE REQUIRED</span><span class="cite">{note}</span>'
    stale = ' <span class="stale">stale</span>' if fig.stale else ""
    src = html.escape(fig.source)
    if fig.as_of:
        asof = f" · {fig.as_of}"
    elif fig.kind == "fundamental":
        asof = ' · <span class="stale">reported date unknown</span>'
    else:
        asof = ""
    note = f' · {html.escape(fig.note)}' if fig.note else ""
    return f'<span class="val">{fmt(fig)}{stale}</span><span class="cite">{src}{asof}{note}</span>'


def kv(label: str, fig: Figure) -> str:
    return f'<div class="kv"><span class="k">{label}</span><span class="v">{datum(fig)}</span></div>'


def slide(eyebrow: str, title: str, body: str, n: int | None = None) -> str:
    sn = f'<span class="sn">{n:02d}</span>' if n is not None else ""
    return (f'<section class="slide"><div class="eyebrow">{eyebrow}{sn}</div>'
            f'<h2>{title}</h2>{body}</section>')


def chip(enforcement: str, text: str) -> str:
    return f'<span class="chip chip-{enforcement}">{html.escape(text)}</span>'


STYLE = """
<style>
:root{
  --bg:#e9edf4; --surface:#ffffff; --ink:#152142; --ink-soft:#5a648a;
  --gold:#9c7a24; --rule:#d3dae8; --ok:#2f7a52; --req:#9a6410; --req-bg:#f6e9cf;
  --block:#a8442f; --block-bg:#f6ddd6; --flag:#9a6410; --flag-bg:#f6e9cf; --mono-ink:#6b7599;
  --serif:"Hoefler Text","Iowan Old Style","Palatino Linotype",Georgia,serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:"SF Mono",ui-monospace,"JetBrains Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#080f24; --surface:#111d42; --ink:#eaeefa; --ink-soft:#9aa6c8;
  --gold:#d2ac57; --rule:#26335c; --ok:#5cc08a; --req:#e8b866; --req-bg:#3a2f14;
  --block:#e0876a; --block-bg:#3a201a; --flag:#e8b866; --flag-bg:#3a2f14; --mono-ink:#8592b8;
}}
:root[data-theme="light"]{
  --bg:#e9edf4; --surface:#ffffff; --ink:#152142; --ink-soft:#5a648a;
  --gold:#9c7a24; --rule:#d3dae8; --ok:#2f7a52; --req:#9a6410; --req-bg:#f6e9cf;
  --block:#a8442f; --block-bg:#f6ddd6; --flag:#9a6410; --flag-bg:#f6e9cf; --mono-ink:#6b7599;
}
:root[data-theme="dark"]{
  --bg:#080f24; --surface:#111d42; --ink:#eaeefa; --ink-soft:#9aa6c8;
  --gold:#d2ac57; --rule:#26335c; --ok:#5cc08a; --req:#e8b866; --req-bg:#3a2f14;
  --block:#e0876a; --block-bg:#3a201a; --flag:#e8b866; --flag-bg:#3a2f14; --mono-ink:#8592b8;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding:40px 20px 80px}
.slide{background:var(--surface);border:1px solid var(--rule);border-radius:10px;
  padding:44px 48px;margin:22px 0;box-shadow:0 1px 3px rgba(10,20,50,.06)}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--gold);display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.sn{color:var(--ink-soft);opacity:.6}
h1{font-family:var(--serif);font-weight:600;font-size:44px;line-height:1.05;margin:.1em 0 .2em;
  text-wrap:balance;letter-spacing:-.01em}
h2{font-family:var(--serif);font-weight:600;font-size:29px;line-height:1.1;margin:0 0 22px;
  text-wrap:balance;letter-spacing:-.01em}
h3{font-family:var(--sans);font-weight:650;font-size:14px;margin:0 0 10px;letter-spacing:.01em}
.cover{background:linear-gradient(150deg,var(--surface),color-mix(in srgb,var(--gold) 8%,var(--surface)));
  padding-top:56px;padding-bottom:56px}
.sub{font-family:var(--serif);font-size:21px;color:var(--ink-soft);margin:.2em 0 1.1em}
.lede{max-width:64ch;color:var(--ink);font-size:15px}
.asof{font-family:var(--mono);font-size:12px;color:var(--mono-ink);margin-top:26px}
.grid4{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:680px){.grid4,.two{grid-template-columns:1fr}}
.stat{background:color-mix(in srgb,var(--gold) 5%,var(--surface));border:1px solid var(--rule);
  border-radius:8px;padding:16px}
.lab{font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
.big{font-family:var(--serif);font-size:27px;font-weight:600;font-variant-numeric:tabular-nums;line-height:1}
.val{display:block;font-variant-numeric:tabular-nums;font-weight:600;font-size:14px}
.cite{display:block;font-family:var(--mono);font-size:10px;color:var(--mono-ink);margin-top:3px;line-height:1.35}
.req{display:inline-block;font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.06em;
  color:var(--req);background:var(--req-bg);border:1px solid color-mix(in srgb,var(--req) 45%,transparent);
  padding:2px 6px;border-radius:4px}
.stale{font-family:var(--mono);font-size:9px;color:var(--req);text-transform:uppercase;letter-spacing:.04em}
.tbl{width:100%;border-collapse:collapse;font-size:13.5px}
.tbl th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--ink-soft);
  border-bottom:1px solid var(--rule);padding:7px 9px}
.tbl td{padding:8px 9px;border-bottom:1px solid var(--rule);vertical-align:top}
.tbl td.num,.tbl th.num{text-align:right;font-variant-numeric:tabular-nums}
.tbl .tot td{font-weight:700;border-top:2px solid var(--gold);border-bottom:none}
.scroll{overflow-x:auto}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.kv{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid var(--rule)}
.kv:last-child{border-bottom:none}.kv .k{font-size:13px;color:var(--ink-soft)}.kv .v{text-align:right}
.note{font-size:12.5px;color:var(--ink-soft);max-width:76ch;margin-top:14px}
.chip{display:inline-block;font-family:var(--mono);font-size:11px;padding:2px 8px;border-radius:4px;margin:3px 0}
.chip-block{color:var(--block);background:var(--block-bg)}
.chip-flag{color:var(--flag);background:var(--flag-bg)}
.chip-disclose{color:var(--ink-soft);background:color-mix(in srgb,var(--ink-soft) 12%,transparent)}
.flagrow{display:flex;gap:10px;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--rule)}
.flagrow:last-child{border-bottom:none}.flagrow .d{font-size:13px}
.warn{color:var(--block);font-family:var(--mono);font-size:12px}
.scorebar{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:18px 26px;
  margin:22px 0;display:flex;gap:26px;flex-wrap:wrap;align-items:center}
.scorebar .big{font-size:22px}.scorebar .lab{margin:0}
</style>
"""
