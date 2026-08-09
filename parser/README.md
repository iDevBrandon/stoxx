# finance-parser

Local, **LLM-free** SEC filing → structured JSON for Oxinion Finance.

Given a 10-K / 10-Q PDF it runs a four-stage pipeline and returns typed,
source-cited data:

```bash
classify   → what is it?            (10-K / 10-Q / 8-K / annual_report)
split      → where is what?         (section page ranges + the big-3 statements)
parse      → what's on the page?    (blocks with bbox, for the viewer overlay)
extract    → the numbers I want     (revenue, net income, total assets, …)
```

No LLM is used anywhere. Two parsing engines live in one codebase and are
selected automatically (see **Engines**).

---

## Requirements

- Python 3.10+
- The slim `requirements.txt` installs **PyMuPDF only** (light, ~130 MB, fits
  512 MB hosts). That alone runs the whole pipeline.
- Docling (better tables/layout) is **optional** — install it separately to
  enable the higher-quality engine (needs ~2 GB RAM).

## Setup

```bash
cd finance-parser
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # PyMuPDF engine
# optional, for Docling-quality parsing:
# pip install docling
```

## Run the API server

```bash
python -m uvicorn finance_parser.main:app --reload --port 8000
```

- Use `python -m uvicorn …` (not bare `uvicorn`) so it uses the venv.
- Open `http://127.0.0.1:8000/health` → `{"ok": true}`.
- Interactive docs (upload + try in the browser): `http://127.0.0.1:8000/docs`.

### Endpoints

| Method | Path         | Body (multipart)              | Returns                                                                                                                         |
| ------ | ------------ | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| GET    | `/health`    | —                             | `{"ok": true}`                                                                                                                  |
| POST   | `/split`     | `file`                        | docType + section page ranges (fast, no Docling)                                                                                |
| POST   | `/parse`     | `file`, `section?`            | blocks with bbox for a section (default: Financial Statements)                                                                  |
| POST   | `/extract`   | `file`, `fields?`, `section?` | field values (revenue, net_income, …) with page citations                                                                       |
| POST   | `/statement` | `file`, `name`                | one statement as rows (`name` = `balance_sheet` / `income_statement` / `cash_flow` / `comprehensive_income` / `equity_changes`) |

Examples:

```bash
# section map (fast)
curl -s -F "file=@filing.pdf" http://localhost:8000/split | jq '.sections'

# extract fields
curl -s -F "file=@filing.pdf" -F "fields=revenue,net_income,total_assets" \
  http://localhost:8000/extract | jq '.fields'

# one statement as rows
curl -s -F "file=@filing.pdf" -F "name=income_statement" \
  http://localhost:8000/statement | jq '.rows[:10]'
```

## Run the CLI (whole pipeline → one JSON)

```bash
python -m finance_parser.run filing.pdf -o result.json
# options:
#   --fields revenue,net_income,total_assets
#   --blocks         include parse blocks for the Financial Statements range
```

`result.json` contains `docType`, `sections`, `fields`, and `statements`
(and `blocks` if `--blocks`). This is what the GitHub Actions worker runs.

## Engines

`parse` (blocks/overlay) has two interchangeable engines; the rest of the
pipeline (`classify` / `split` / `extract` / `statement`) is always PyMuPDF.

| Engine  | Quality     | RAM     | When                                                |
| ------- | ----------- | ------- | --------------------------------------------------- |
| PyMuPDF | good        | ~100 MB | default; free hosts (Render free)                   |
| Docling | best tables | ~2 GB   | when `docling` is installed (local, GitHub Actions) |

Selection is automatic: **Docling if it can be imported, otherwise PyMuPDF.**
Override explicitly:

```bash
PARSER_ENGINE=pymupdf python -m uvicorn finance_parser.main:app --port 8000
PARSER_ENGINE=docling  python -m finance_parser.run filing.pdf --blocks
```

If Docling is selected but fails at runtime (memory/model), it falls back to
PyMuPDF automatically.

## Deploy (Render, free)

The slim `requirements.txt` + `render.yaml` deploy the PyMuPDF engine on
Render's free tier (512 MB — plenty; the server idles at ~100 MB).

1. Push this repo to GitHub.
2. Render → **New → Blueprint** → pick the repo → **Apply** (reads `render.yaml`).
3. After build, check `https://<your-service>.onrender.com/health`.

Note: the free tier sleeps after ~15 min idle, so the first request is slow
(~30–60 s) then fast.

### Connect the Studio front-end

In the client (`oxinion-finance-client`) set:

```bash
NEXT_PUBLIC_PARSER_URL = https://<your-service>.onrender.com
```

and redeploy. `finance.oxinion.com/datasets/studio` then calls this server.
CORS already allows `localhost` and `finance.oxinion.com`.

## Output schema (`ParseResult`)

```jsonc
{
  "docType": "10-Q",
  "docTypeConfidence": 0.98,
  "numPages": 91,
  "sections": [
    {
      "name": "financial_statements",
      "label": "Financial Statements",
      "startPage": 3,
      "endPage": 22,
      "confidence": 0.95,
    },
    {
      "name": "balance_sheet",
      "label": "Balance Sheet",
      "startPage": 3,
      "endPage": 3,
      "confidence": 0.95,
    },
    // … income_statement, cash_flow, notes, mdna, …
  ],
  "blocks": [
    {
      "id": 1,
      "type": "Table",
      "page": 3,
      "bbox": { "x": 0.06, "y": 0.15, "w": 0.88, "h": 0.44 },
      "text": "…",
      "confidence": 0.8,
    },
  ],
  "parsedPages": [3, 22],
}
```

`bbox` is normalized 0–1, top-left origin — the same shape the Studio overlay
uses, so no reshaping on the client.

## Notes / roadmap

- Section/statement patterns are tuned to the SEC 10-K / 10-Q form (works
  across companies, not just one). IFRS/annual reports have starter patterns.
- `extract` is rules-based; EBITDA is derived (not a printed line) and may be
  absent. Segment-heavy revenue (e.g. Berkshire) can be approximate.
- `.github/workflows/parse.yml` runs the CLI with Docling on GitHub's 8 GB
  runner for occasional high-quality / batch parsing.
