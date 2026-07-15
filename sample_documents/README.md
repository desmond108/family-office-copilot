# Sample documents (for testing the uploaders)

Synthetic test files for the sidebar **Research documents** (section 2) and **Other
documents** (section 3) uploaders. They are coherent with the built-in Kadir /
UOB scenario (target 10% money market · 20% gold · 20% bonds · 20% Nasdaq-100 ·
30% S&P 500, with the pullback / gold-below-$4,000 / tranches asks), so the AI
Model has relevant context to weave into the proposal narrative.

All files are read **without an API key** — plain-text, Markdown, HTML and `.eml`
are decoded deterministically by `doc_extract.py`, and **PDFs** are read via `pypdf`
(the text layer, no vision model needed). Everything is folded into the prompt as
**advisory context — never a source of figures**. No real client data.

Several documents ship in **two formats** so you can exercise each ingestion path
(the `.pdf` twins carry a real, selectable text layer). Upload whichever you like.

## research/ — upload under "2 · Research documents"
| File | Format(s) | What it is |
| --- | --- | --- |
| `Meridian_CIO_Market_Outlook_Q3_2026` | `.md` + `.pdf` | House CIO quarterly outlook & positioning |
| `Northwood_US_Treasury_5yr_Bond_ETF_Factsheet` | `.html` | Low-fee medium-duration bond ETF factsheet (fictional fund) |
| `Alpine_Global_Research_Gold_Strategy_Note` | `.txt` | Third-party gold strategy note & levels (fictional firm) |

## other/ — upload under "3 · Other documents"
| File | Format(s) | What it is |
| --- | --- | --- |
| `Client_Email_Kadir_260705` | `.eml` + `.pdf` | Client email: preferences, pullback rule, Q4 liquidity event |
| `Client_Review_Meeting_Notes_260703` | `.md` + `.pdf` | Review-call notes: objectives, risk, action items |
| `RM_Internal_Note_Kadir` | `.txt` | Internal RM note: tax status, constraints, dry powder |

The `.pdf` twins are generated from the `.md` / `.eml` sources by `build_pdfs.py`
(`python3 sample_documents/build_pdfs.py`, uses reportlab). Delete the sources if
you'd rather keep only the PDFs.

## How to test
1. In the sidebar, load a sample statement (e.g. **UOB Private Bank**) and press **Analyse ▸**.
2. Upload the `research/` files under section 2 and the `other/` files under section 3 —
   each shows a ✅ "text read" status with a character count.
3. Open **Proposal** → **🧠 The prompt handed to the AI**: the documents appear in full
   under the `RESEARCH DOCUMENTS` and `OTHER DOCUMENTS` blocks.
4. Press **✨ Generate with AI Model** (or copy the prompt into any AI model) and see how
   the narrative reflects the documents — while every figure stays deterministic.
