"""deck_data.py — regenerate the data-bearing deck slides (3, 6, 8) from
datafeed.py, with a provenance footnote on every figure.

Contrast with the original Fable deck: there, gold $4,067 / P/E 20.1x / SGOV
0.09% fee were all LLM-recalled. Here each cell is a Figure; sourced ones show
the value + citation, unsourced ones show [SOURCE REQUIRED]. A compliance officer
can sign the sourced cells and knows exactly which cells still need a feed.

Run:  python3 deck_data.py     (needs network; sandbox-off)
"""
from __future__ import annotations

from datafeed import Feed, Figure, required


def _line(label: str, fig: Figure, width: int = 34) -> str:
    flag = "  ⚠STALE" if fig.stale else ""
    return f"  {label:<{width}} {fig.text():>16}{flag}   ·  {fig.cite()}"


def slide3_macro(feed: Feed) -> list[str]:
    figs = {
        "Fed funds target (upper)":   feed.fred("DFEDTARU"),
        "Fed funds target (lower)":   feed.fred("DFEDTARL"),
        "10-yr Treasury yield":       feed.fred("DGS10"),
        "Spot gold (COMEX front)":    feed.last_close("GC=F", "USD/oz"),
        "S&P 500 index level":        feed.last_close("^GSPC", ""),
        "Nasdaq-100 index level":     feed.last_close("^NDX", ""),
        # Not obtainable from price/macro feeds — must stay honest:
        "Market-implied hike odds":   required("CME FedWatch — not in yfinance/FRED"),
        "S&P 500 FORWARD P/E":        required("needs forward EPS estimates (FMP/Refinitiv)"),
    }
    return ["SLIDE 3 — Macro Environment"] + [_line(k, v) for k, v in figs.items()]


def slide6_bonds(feed: Feed) -> list[str]:
    out = ["SLIDE 6 — Bond ETF Comparison"]
    for t in ("VCIT", "BND", "AGG", "IEF"):
        er = feed.expense_ratio(t)                          # live (yfinance .info)
        dur = feed.reference(t, "effective_duration", "yr")  # table/SOURCE_REQUIRED
        sec = feed.dist_yield(t)                            # live proxy (yfinance .info)
        aum = feed.fund_field(t, "totalAssets", "USD")     # live where available
        navimp = feed.nav_impact_per_100bp(dur)            # derived from duration
        out.append(f"  {t}:")
        out.append(_line("   expense ratio", er))
        out.append(_line("   effective duration", dur))
        out.append(_line("   yield (distribution proxy)", sec))
        out.append(_line("   AUM (live)", aum))
        out.append(_line("   NAV impact @ +100bp", navimp))
    return out


def slide8_gold(feed: Feed) -> list[str]:
    out = ["SLIDE 8 — Gold ETF Selection"]
    spot = feed.last_close("GC=F", "USD/oz")
    out.append(_line("Spot gold (COMEX front)", spot))
    for t in ("GLDM", "IAU", "GLD"):
        er = feed.expense_ratio(t)                          # live (yfinance .info)
        aum = feed.fund_field(t, "totalAssets", "USD")
        px = feed.last_close(t, "USD")
        out.append(f"  {t}:")
        out.append(_line("   expense ratio", er))
        out.append(_line("   AUM (live)", aum))
        out.append(_line("   last price (live)", px))
    return out


if __name__ == "__main__":
    feed = Feed()
    print("=" * 100)
    print("PROVENANCE-BACKED DECK DATA  ·  sourced cells carry a citation; "
          "unsourced cells say [SOURCE REQUIRED]")
    print("=" * 100)
    for builder in (slide3_macro, slide6_bonds, slide8_gold):
        print()
        for row in builder(feed):
            print(row)

    # Honesty scorecard: how much of the deck's data is actually sourced?
    feed2 = Feed()
    all_figs = []
    for b in (slide3_macro, slide6_bonds, slide8_gold):
        b(feed2)  # (re-evaluated inside; we recount below for a clean tally)
    # Recount explicitly:
    checks = [
        feed2.fred("DFEDTARU"), feed2.fred("DGS10"),
        feed2.last_close("GC=F"), feed2.last_close("^GSPC"),
        feed2.expense_ratio("VCIT"), feed2.dist_yield("VCIT"),
        feed2.reference("VCIT", "effective_duration"),   # the one still unsourced
        feed2.fund_field("GLD", "totalAssets"),
    ]
    ok = sum(1 for f in checks if f.ok)
    print("\n" + "-" * 100)
    print(f"SCORECARD (sample of {len(checks)} figures): {ok} sourced, "
          f"{len(checks) - ok} need a feed.  "
          "The [SOURCE REQUIRED] cells are the exact reference-data gap to close.")
