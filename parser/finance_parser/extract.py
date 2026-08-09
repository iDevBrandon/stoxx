"""extract — pull specific financial fields from a section's page range. No LLM
(MVP).

Two things make this robust enough for real statements:
  1. Rows are reconstructed from word coordinates (PyMuPDF "words"), so a table
     whose label and figures land in separate text lines (columnar layout) is
     put back together as one visual row.
  2. A line only counts if it STARTS with a field label AND ENDS with a number
     — that keeps real statement rows ("Total assets  $ 1,252,271  1,222,176")
     and rejects prose ("Net earnings of pipelines increased $118 million…")
     and note headings ("Note 23. Revenues from contracts…").

Line-item naming still varies by company/GAAP and some metrics (EBITDA) are
derived, not printed — those come back found: false for now.
"""

from __future__ import annotations

import re

import fitz  # PyMuPDF

from .schema import ExtractField, StatementRow

FIELD_LABELS: dict[str, str] = {
    "revenue": "Revenue",
    "gross_profit": "Gross profit",
    "operating_income": "Operating income",
    "net_income": "Net income",
    "total_assets": "Total assets",
    "ebitda": "EBITDA",
}

# Matched against normalized line text; must appear at the START of the line.
FIELD_PATTERNS: dict[str, list[str]] = {
    "revenue": [
        "total revenues",
        "total revenue",
        "total net sales",
        "net sales",
        "revenue",
        "revenues",
    ],
    "gross_profit": ["gross profit", "gross margin"],
    "operating_income": [
        "operating income",
        "income from operations",
        "operating profit",
    ],
    "net_income": [
        "net earnings attributable",
        "net income attributable",
        "net earnings",
        "net income",
    ],
    "total_assets": ["total assets"],
    # EBITDA is almost never printed — derive later (Op income + D&A).
    "ebitda": [],
}

DEFAULT_FIELDS = list(FIELD_LABELS.keys())

_SKIP = (
    "per share",
    "per diluted",
    "earnings per",
    "weighted average",
    "shares outstanding",
)

# Money token: optional ( $ - , digits , decimals , )
_NUM = re.compile(r"\(?\$?\s?-?\d[\d,]*(?:\.\d+)?\)?")


def _norm(s: str) -> str:
    s = re.sub(r"[^\x20-\x7e]", "", s)  # printable ASCII only (drop smart/control apostrophes)
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = re.sub(r"\b(condensed|unaudited)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _reconstruct_rows(page) -> list[str]:
    """Rebuild visual rows from word coordinates so columnar tables (label in
    one column, figures in others) come back as one line."""
    words = page.get_text("words")  # (x0, y0, x1, y1, word, block, line, wordno)
    if not words:
        return [ln for ln in page.get_text("text").splitlines() if ln.strip()]

    words.sort(key=lambda w: (w[1], w[0]))
    rows: list[list] = []
    cur: list = []
    base: float | None = None
    for w in words:
        if base is None or abs(w[1] - base) <= 3:  # same row within 3pt
            cur.append(w)
            if base is None:
                base = w[1]
        else:
            rows.append(cur)
            cur = [w]
            base = w[1]
    if cur:
        rows.append(cur)

    return [
        " ".join(w[4] for w in sorted(r, key=lambda w: w[0])) for r in rows
    ]


def _ends_with_number(line: str) -> bool:
    return bool(re.search(r"[\d)]\s*$", line.strip()))


def _first_number(raw: str) -> tuple[str, float] | None:
    for m in _NUM.finditer(raw):
        tok = m.group(0).strip()
        digits = re.sub(r"[^\d.]", "", tok)
        if not digits or digits == ".":
            continue
        try:
            val = float(digits)
        except ValueError:
            continue
        if tok.startswith("(") or tok.startswith("-") or tok.endswith(")"):
            val = -val
        return tok, val
    return None


def extract_fields(
    path: str, fields: list[str], pages: tuple[int, int]
) -> list[ExtractField]:
    doc = fitz.open(path)
    hi = min(pages[1], doc.page_count)
    found: dict[str, ExtractField] = {}

    for pno in range(pages[0], hi + 1):
        for raw in _reconstruct_rows(doc[pno - 1]):
            line = _norm(raw)
            if not line or any(s in line for s in _SKIP):
                continue
            # Real statement row: starts with a label, ends with a figure.
            if not _ends_with_number(line):
                continue
            for key in fields:
                if key in found:
                    continue
                for pat in FIELD_PATTERNS.get(key, []):
                    if not line.startswith(pat):
                        continue
                    num = _first_number(raw)
                    if num is None:
                        continue
                    disp, val = num
                    found[key] = ExtractField(
                        key=key,
                        label=FIELD_LABELS.get(key, key),
                        found=True,
                        value=disp,
                        number=val,
                        page=pno,
                        line=raw.strip()[:200],
                        confidence=0.9,
                    )
                    break

    doc.close()

    return [
        found.get(
            key,
            ExtractField(
                key=key, label=FIELD_LABELS.get(key, key), found=False, confidence=0.0
            ),
        )
        for key in fields
    ]


def extract_statement(path: str, pages: tuple[int, int]) -> list[StatementRow]:
    """Return every line item of a statement as label + figures, using the same
    row reconstruction as field extraction (handles columnar layouts)."""
    doc = fitz.open(path)
    hi = min(pages[1], doc.page_count)
    rows: list[StatementRow] = []

    for pno in range(pages[0], hi + 1):
        for raw in _reconstruct_rows(doc[pno - 1]):
            if not raw.strip():
                continue
            nums = [
                m.group(0).strip()
                for m in _NUM.finditer(raw)
                if re.sub(r"[^\d.]", "", m.group(0)) not in ("", ".")
            ]
            if not nums:
                continue
            first = _NUM.search(raw)
            label = raw[: first.start()].strip(" .$")
            # keep rows that read like a line item (have a text label)
            if not label or not re.search(r"[a-zA-Z]", label):
                continue
            rows.append(
                StatementRow(label=label[:120], values=nums[:4], page=pno)
            )

    doc.close()
    return rows
