"""build_statements.py — render the three synthetic tuned statements as realistic,
print-ready HTML (one per custodian), for training family-office staff.

Each looks like that custodian's real statement, but with confidential fields
REDACTED (black bars + margin labels) and a legend explaining what tuning removes
(client name, address, account number, RM) vs. retains (holdings, quantities,
valuations, currencies). The holdings data matches the parser inputs exactly, so
staff can see the same statements the pipeline ingests.

Writes _statements_html/*.html; convert to PDF with Chrome (see make_statement_pdfs.sh).
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "synthetic_statements"
OUT = HERE / "_statements_html"
OUT.mkdir(exist_ok=True)

REDACT = '<span class="redact" title="redacted confidential data">&nbsp;</span>'

BASE_CSS = """
<style>
@page { size: A4; margin: 16mm 15mm; }
*{ box-sizing:border-box; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
body{ margin:0; color:#1a2230; font:13px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
.sample{ background:#b5231f; color:#fff; text-align:center; font-weight:700; letter-spacing:.14em;
  font-size:11px; padding:5px; text-transform:uppercase; }
.doc{ padding:20px 26px; }
.head{ display:flex; justify-content:space-between; align-items:flex-start; border-bottom:3px solid var(--brand);
  padding-bottom:12px; margin-bottom:16px; }
.brand{ font-weight:800; font-size:20px; color:var(--brand); letter-spacing:-.01em; }
.brand .sub{ display:block; font-weight:600; font-size:11px; color:#6b7386; letter-spacing:.12em;
  text-transform:uppercase; margin-top:3px; }
.title{ text-align:right; }
.title h1{ margin:0; font-size:17px; }
.title .per{ font-size:12px; color:#6b7386; }
.parties{ display:flex; gap:24px; margin-bottom:14px; }
.party{ flex:1; background:#f4f6fa; border:1px solid #e2e7f0; border-radius:6px; padding:11px 13px; }
.party h4{ margin:0 0 7px; font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:#8a92a6; }
.row{ display:flex; gap:8px; margin:3px 0; font-size:12px; }
.row .k{ color:#8a92a6; min-width:96px; }
.redact{ display:inline-block; min-width:120px; height:12px; background:repeating-linear-gradient(
  45deg,#20242e,#20242e 5px,#33384a 5px,#33384a 10px); border-radius:2px; vertical-align:middle; }
.tag{ font-size:9.5px; color:#b5231f; font-weight:700; margin-left:6px; vertical-align:middle; }
table{ width:100%; border-collapse:collapse; margin:6px 0 4px; }
th{ text-align:left; font-size:9.5px; text-transform:uppercase; letter-spacing:.05em; color:#8a92a6;
  border-bottom:1.5px solid var(--brand); padding:7px 6px; }
td{ padding:7px 6px; border-bottom:1px solid #e8ebf2; font-size:12px; }
td.n,th.n{ text-align:right; font-variant-numeric:tabular-nums; }
.tot td{ font-weight:700; border-top:2px solid var(--brand); border-bottom:none; }
.sec{ font-size:10px; letter-spacing:.06em; text-transform:uppercase; color:var(--brand); font-weight:700;
  margin:16px 0 2px; }
.legend{ margin-top:16px; background:#fff8ec; border:1px solid #f0dcae; border-radius:6px; padding:11px 14px;
  font-size:11px; color:#5a4a25; }
.legend b{ color:#3a2f10; }
.legend .keep{ color:#2f7a52; font-weight:700; }
.legend .cut{ color:#b5231f; font-weight:700; }
.foot{ margin-top:14px; font-size:9.5px; color:#9aa0b0; border-top:1px solid #e8ebf2; padding-top:8px; }
.note{ font-size:10px; color:#8a92a6; font-style:italic; }
</style>
"""

LEGEND = ('<div class="legend"><b>Training note — this is a TUNED statement.</b> '
          '<span class="cut">Removed (confidential):</span> client name, residential address, '
          'account number, relationship-manager name, contact details. '
          '<span class="keep">Retained (needed for analysis):</span> instrument names &amp; codes, '
          'quantities/nominal, prices, currencies, valuations and dates. The black bars mark '
          'redacted fields — learn to confirm every one is removed before a statement leaves the office.</div>')


def read_csv(path: Path, sep: str, comma_dec: bool):
    text = path.read_text()
    rows = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    def num(s): return float(s.replace(",", ".")) if comma_dec else float(s)
    return list(csv.DictReader(rows, delimiter=sep)), num


def money(x, ccy="USD"):
    return f"{x:,.2f} {ccy}"


def doc(brand_color, brand, sub, title, period, parties, body):
    return (f'<!doctype html><html><head><meta charset="utf-8">{BASE_CSS}'
            f'<style>:root{{--brand:{brand_color}}}</style></head><body>'
            f'<div class="sample">Sample · Tuned for training · not a live account</div>'
            f'<div class="doc"><div class="head">'
            f'<div class="brand">{brand}<span class="sub">{sub}</span></div>'
            f'<div class="title"><h1>{title}</h1><div class="per">{period}</div></div></div>'
            f'{parties}{body}{LEGEND}'
            f'<div class="foot">Statement generated for educational use. Figures are illustrative. '
            f'This document does not constitute advice, an offer, or a solicitation.</div>'
            f'</div></body></html>')


def parties_block(rows):
    left = "".join(f'<div class="row"><span class="k">{k}</span><span>{v}</span></div>' for k, v in rows[0])
    right = "".join(f'<div class="row"><span class="k">{k}</span><span>{v}</span></div>' for k, v in rows[1])
    return (f'<div class="parties"><div class="party"><h4>Account holder</h4>{left}</div>'
            f'<div class="party"><h4>Account &amp; custody</h4>{right}</div></div>')


# --------------------------------------------------------------------------- #
# A — UOB Private Bank (Singapore, USD, per-share)
# --------------------------------------------------------------------------- #
def statement_a():
    rows, num = read_csv(SRC / "custodianA_uob.csv", ",", False)
    trs, total = "", 0.0
    for r in rows:
        qty, price = num(r["quantity"]), num(r["price"])
        val = qty * price
        total += val
        trs += (f'<tr><td>{html.escape(r["name"])}</td>'
                f'<td>{r["identifier"]} <span class="note">({r["id_type"]})</span></td>'
                f'<td>{r["asset_class"]}</td><td class="n">{qty:,.0f}</td>'
                f'<td class="n">{price:,.2f}</td><td class="n">{val:,.2f}</td></tr>')
    trs += f'<tr class="tot"><td colspan="5">Total portfolio value (USD)</td><td class="n">{total:,.2f}</td></tr>'
    parties = parties_block([
        [("Name", REDACT + '<span class="tag">redacted</span>'),
         ("Address", REDACT), ("Residence", REDACT)],
        [("Account no.", '****‑****‑' + REDACT + '<span class="tag">redacted</span>'),
         ("Base currency", "USD"), ("Adviser (RM)", REDACT), ("As of", "02 Jul 2026")]])
    body = (f'<div class="sec">Holdings</div>'
            f'<table><thead><tr><th>Security</th><th>Identifier</th><th>Asset class</th>'
            f'<th class="n">Quantity</th><th class="n">Price (USD)</th><th class="n">Value (USD)</th>'
            f'</tr></thead><tbody>{trs}</tbody></table>'
            f'<p class="note">Prices quoted per share; money-market and cash lines valued at par.</p>')
    return doc("#c8102e", "UOB", "Private Bank · Singapore",
               "Portfolio Holdings Statement", "Period ending 02 July 2026", parties, body)


# --------------------------------------------------------------------------- #
# B — Banque Privée (European, EUR/CHF, bonds in % of nominal, house codes)
# --------------------------------------------------------------------------- #
def statement_b():
    rows, num = read_csv(SRC / "custodianB_eurobank.csv", ";", True)
    trs = ""
    for r in rows:
        qty, cours = num(r["nominal_ou_qte"]), num(r["cours"])
        basis = r["base_valo"]
        val = qty * cours / 100 if basis == "pct_nominal" else qty * cours
        cours_disp = f'{cours:,.3f} %' if basis == "pct_nominal" else f'{cours:,.2f}'
        code = r["code"]
        code_tag = "" if r["code_type"] == "ISIN" else ' <span class="tag">code interne</span>'
        trs += (f'<tr><td>{html.escape(r["libelle"])}</td>'
                f'<td>{code}{code_tag}</td><td>{r["classe"]}</td>'
                f'<td class="n">{qty:,.0f}</td><td class="n">{cours_disp}</td>'
                f'<td>{r["devise"]}</td><td class="n">{val:,.2f}</td></tr>')
    parties = parties_block([
        [("Titulaire", REDACT + '<span class="tag">masqué</span>'),
         ("Adresse", REDACT), ("Domicile", REDACT)],
        [("N° de compte", REDACT + '<span class="tag">masqué</span>'),
         ("Devise de réf.", "USD"), ("Conseiller", REDACT), ("Au", "02.07.2026")]])
    body = (f'<div class="sec">Positions du portefeuille</div>'
            f'<table><thead><tr><th>Désignation</th><th>Code</th><th>Catégorie</th>'
            f'<th class="n">Nominal / Qté</th><th class="n">Cours</th><th>Devise</th>'
            f'<th class="n">Valeur (devise)</th></tr></thead><tbody>{trs}</tbody></table>'
            f'<p class="note">Obligations valorisées en % du nominal. Valeurs exprimées en devise '
            f'de la position; conversion en USD effectuée par la banque au taux du jour. '
            f'Total déclaré (contre-valeur USD): 639 050,00.</p>')
    return doc("#1f3a5f", "Banque Privée", "Genève",
               "Relevé de portefeuille", "Arrêté au 02 juillet 2026", parties, body)


# --------------------------------------------------------------------------- #
# C — Alpine Trust Services (family-office SPV, alternatives + Lombard loan)
# --------------------------------------------------------------------------- #
def statement_c():
    d = json.loads((SRC / "custodianC_familyoffice.json").read_text())
    trs, total = "", 0.0
    for p in d["positions"]:
        total += p["nav_usd"]
        stale = ""
        # flag old marks so staff learn illiquid valuations lag
        trs += (f'<tr><td>{html.escape(p["name"])}</td><td>{p["asset_class"]}</td>'
                f'<td>{p["valuation"].replace("_"," ")}</td>'
                f'<td class="n">{p["nav_usd"]:,.2f}</td><td class="n">{p["nav_as_of"]}</td></tr>')
    trs += f'<tr class="tot"><td colspan="3">Total investments (USD)</td><td class="n">{total:,.2f}</td><td></td></tr>'
    liab = ""
    for lb in d["liabilities"]:
        liab += (f'<tr><td>{lb["type"].replace("_"," ").title()}</td><td>{lb["currency"]}</td>'
                 f'<td class="n">{lb["balance"]:,.2f}</td><td class="n">{lb["rate"]:.2%}</td></tr>')
    net = total - sum(abs(lb["balance"]) for lb in d["liabilities"])
    parties = parties_block([
        [("Beneficial owner", REDACT + '<span class="tag">redacted</span>'),
         ("Settlor", REDACT), ("Correspondence", REDACT)],
        [("Entity", d["entity"] + '<span class="tag">retained</span>'),
         ("Structure", "SPV / Trust"), ("Trustee contact", REDACT), ("As of", "02 Jul 2026")]])
    body = (f'<div class="sec">Investments — manual valuations</div>'
            f'<table><thead><tr><th>Holding</th><th>Class</th><th>Valuation basis</th>'
            f'<th class="n">NAV (USD)</th><th class="n">NAV date</th></tr></thead><tbody>{trs}</tbody></table>'
            f'<div class="sec">Financing</div>'
            f'<table><thead><tr><th>Facility</th><th>Ccy</th><th class="n">Balance (USD)</th>'
            f'<th class="n">Rate</th></tr></thead><tbody>{liab}</tbody></table>'
            f'<p class="note">Net asset value after financing: {net:,.2f} USD. Alternatives and direct '
            f'real estate carry manual NAVs struck at the dates shown — these lag public markets and '
            f'should be treated as stale between valuation cycles. The entity name is retained (it is '
            f'not personal data); the underlying individuals are redacted.</p>')
    return doc("#2f5d50", "Alpine Trust", "Services · SPV Administration",
               "Statement of Trust Assets", "As at 02 July 2026", parties, body)


if __name__ == "__main__":
    for name, fn in [("A_uob", statement_a), ("B_banque_privee", statement_b),
                     ("C_alpine_trust", statement_c)]:
        (OUT / f"{name}.html").write_text(fn())
        print("wrote", OUT / f"{name}.html")
