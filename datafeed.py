"""datafeed.py — provenance-first market/reference data layer.

Every number a client document shows must carry {value, source, as_of}. The
whole point: when a figure has no trustworthy source, the feed returns a
SOURCE_REQUIRED sentinel that renders as "[SOURCE REQUIRED]" — never a plausible
hallucinated value. This is the antidote to the original Fable deck, where market
figures AND product facts were LLM-recalled.

Providers are injectable (like Portfolio_Mgr/marketdata.py and Hedge_Fund/
providers.py) so tests run offline. Live providers:
  - yfinance        -> last close, fund AUM/yield/NAV  (free, no key)
  - FRED            -> macro series (rates, etc.)       (needs FRED_API_KEY)
  - reference table -> fees/durations, from a VERIFIED json you supply (else
                       SOURCE_REQUIRED — we do NOT bake in remembered fund facts)

Market-closed handling: as_of comes from the data (last trading day). If it is
older than today, the figure is flagged stale (e.g. US markets shut for a holiday).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

SOURCE_REQUIRED = "SOURCE_REQUIRED"

# Where to look for API keys: env first, then the sibling repos' key files.
_KEY_DIRS = [
    Path(__file__).resolve().parent,
    Path(__file__).resolve().parent.parent / "Hedge_Fund_260701",
    Path(__file__).resolve().parent.parent / "Portfolio_Mgr_260627",
]


def resolve_key(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name].strip()
    for d in _KEY_DIRS:
        p = d / name
        if p.is_file():
            v = p.read_text().strip()
            if v:
                return v
    return None


# --------------------------------------------------------------------------- #

@dataclass
class Figure:
    """One data point with its provenance. `value is None` + SOURCE_REQUIRED
    source means 'we could not source this — do not invent it'."""
    value: object | None = None
    unit: str = ""
    source: str = SOURCE_REQUIRED
    as_of: str | None = None
    note: str = ""
    kind: str = "static"   # price | macro | fundamental | derived | static

    # Max age (days) before a figure is "stale" — differs by data category.
    # A price 2 days old means the market was closed; a quarterly factsheet
    # 90 days old is normal and expected, NOT stale.
    _TOL = {"price": 1, "macro": 5, "fundamental": 100, "derived": 100, "static": 10**6}

    @property
    def ok(self) -> bool:
        return self.source != SOURCE_REQUIRED and self.value is not None

    @property
    def age_days(self) -> int | None:
        if not self.as_of:
            return None
        try:
            return (date.today() - datetime.fromisoformat(self.as_of).date()).days
        except ValueError:
            return None

    @property
    def stale(self) -> bool:
        age = self.age_days
        return age is not None and age > self._TOL.get(self.kind, 1)

    def text(self) -> str:
        if not self.ok:
            return "[SOURCE REQUIRED]"
        if isinstance(self.value, float):
            v = f"{self.value:,.2f}" if self.unit != "%" else f"{self.value:.2f}%"
        else:
            v = str(self.value)
        if self.unit and self.unit != "%":
            v = f"{v} {self.unit}".strip()
        return v

    def cite(self) -> str:
        if not self.ok:
            return "no source available"
        tag = f"{self.source}"
        if self.as_of:
            tag += f", as of {self.as_of}"
            if self.stale:
                tag += (" (last close — market closed since)" if self.kind in ("price", "macro")
                        else " (verify a newer figure hasn't published)")
        elif self.kind == "fundamental":
            tag += ", reported date unknown"   # honest: provider gives no timestamp
        if self.note:
            tag += f" — {self.note}"
        return tag


def required(note: str = "") -> Figure:
    return Figure(source=SOURCE_REQUIRED, note=note)


# --------------------------------------------------------------------------- #
# Live feed
# --------------------------------------------------------------------------- #

class Feed:
    """Live providers. Any failure degrades to SOURCE_REQUIRED — never a guess."""

    def __init__(self, reference_path: str | None = None):
        self._ref = {}
        self._info_cache: dict[str, dict] = {}
        # Optional VERIFIED reference table (fees/durations) with per-row citation.
        rp = Path(reference_path) if reference_path else Path(__file__).with_name("reference_table.json")
        if rp.is_file():
            self._ref = json.loads(rp.read_text())

    def _info(self, ticker: str) -> dict:
        if ticker not in self._info_cache:
            try:
                import yfinance as yf
                self._info_cache[ticker] = yf.Ticker(ticker).info or {}
            except Exception:  # noqa: BLE001
                self._info_cache[ticker] = {}
        return self._info_cache[ticker]

    def expense_ratio(self, ticker: str) -> Figure:
        """Net expense ratio from yfinance .info (already in percent units)."""
        v = self._info(ticker).get("netExpenseRatio")
        if v is None:
            return required(f"no expense ratio for {ticker}")
        # yfinance .info has no timestamp — do NOT stamp today() (false freshness).
        return Figure(round(float(v), 3), "%", "yfinance .info[netExpenseRatio]",
                      as_of=None, note="net expense ratio", kind="fundamental")

    def dist_yield(self, ticker: str) -> Figure:
        """Trailing distribution yield (proxy for 30-day SEC yield; label it honestly)."""
        v = self._info(ticker).get("yield")
        if v is None:
            return required(f"no yield for {ticker}")
        return Figure(round(float(v) * 100, 2), "%", "yfinance .info[yield]",
                      as_of=None, kind="fundamental",
                      note="trailing distribution yield — NOT the official 30-day SEC yield")

    # ---- prices (yfinance) ------------------------------------------------ #
    def last_close(self, ticker: str, unit: str = "USD") -> Figure:
        try:
            import yfinance as yf
            h = yf.download(ticker, period="7d", interval="1d",
                            progress=False, auto_adjust=True)
            if h.empty:
                return required(f"yfinance returned no rows for {ticker}")
            close = h["Close"].dropna()
            last = float(close.iloc[-1].item())
            asof = close.index[-1].date().isoformat()
            return Figure(round(last, 2), unit, "yfinance", asof, kind="price")
        except Exception as e:  # noqa: BLE001 — degrade, don't crash
            return required(f"yfinance error: {type(e).__name__}")

    def fund_field(self, ticker: str, field: str, unit: str = "") -> Figure:
        """Live fund facts yfinance actually carries: totalAssets, yield, navPrice."""
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info
            val = info.get(field)
            if val is None:
                return required(f"yfinance .info has no '{field}' for {ticker}")
            # .info carries no timestamp — as_of=None, flagged fundamental.
            return Figure(val, unit, f"yfinance .info[{field}]", as_of=None, kind="fundamental")
        except Exception as e:  # noqa: BLE001
            return required(f"yfinance error: {type(e).__name__}")

    # ---- macro (FRED) ----------------------------------------------------- #
    def fred(self, series_id: str, unit: str = "%") -> Figure:
        key = resolve_key("FRED_API_KEY")
        if not key:
            return required("FRED_API_KEY not found")
        try:
            import ssl
            import urllib.request
            import certifi
            url = ("https://api.stlouisfed.org/fred/series/observations"
                   f"?series_id={series_id}&api_key={key}&file_type=json"
                   "&sort_order=desc&limit=1")
            ctx = ssl.create_default_context(cafile=certifi.where())
            d = json.load(urllib.request.urlopen(url, timeout=15, context=ctx))
            obs = d["observations"][0]
            if obs["value"] in (".", ""):
                return required(f"FRED {series_id} latest obs is missing")
            return Figure(round(float(obs["value"]), 2), unit,
                          f"FRED:{series_id}", obs["date"], kind="macro")
        except Exception as e:  # noqa: BLE001
            return required(f"FRED error: {type(e).__name__}")

    # ---- reference facts (verified table only; else SOURCE_REQUIRED) ------ #
    def reference(self, ticker: str, field: str, unit: str = "") -> Figure:
        row = self._ref.get(ticker, {})
        if field in row and "source" in row:
            return Figure(row[field], unit, row["source"], row.get("as_of"),
                          note="verified reference table", kind="fundamental")
        return required(f"no free feed carries {ticker}.{field} "
                        "(Polygon lacks it; FMP paid tier only) — "
                        "load a factsheet value into reference_table.json")

    # ---- derived (propagates provenance from inputs) ---------------------- #
    @staticmethod
    def nav_impact_per_100bp(duration: Figure) -> Figure:
        """Deterministic: a +100bp parallel move costs ~ -duration% of NAV."""
        if not duration.ok:
            return required("depends on effective duration, which is unsourced")
        return Figure(round(-float(duration.value), 2), "%", "derived",
                      duration.as_of, kind="derived",
                      note=f"first-order (−duration; parallel shift, ignores convexity); "
                           f"duration from {duration.source}")
