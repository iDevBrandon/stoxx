"""CLI — run the whole pipeline on one PDF and emit a single JSON.

    python -m finance_parser.run input.pdf -o result.json [--blocks]

Used by the GitHub Actions worker (Docling available on the 8GB runner). The
`--blocks` (Docling) step is optional and imported lazily so classify/split/
extract/statement work even without Docling installed.
"""

from __future__ import annotations

import argparse
import json
import sys

from .classify import classify_pdf, taxonomy_key
from .extract import DEFAULT_FIELDS, extract_fields, extract_statement
from .split import page_count, split_pdf

STATEMENT_NAMES = (
    "balance_sheet",
    "income_statement",
    "comprehensive_income",
    "equity_changes",
    "cash_flow",
)


def build_result(pdf: str, fields: list[str], include_blocks: bool) -> dict:
    doc_type, conf = classify_pdf(pdf)
    total = page_count(pdf)
    sections = split_pdf(pdf, taxonomy_key(doc_type))

    result: dict = {
        "docType": doc_type,
        "docTypeConfidence": conf,
        "numPages": total,
        "sections": [s.model_dump() for s in sections],
    }

    fs = next((s for s in sections if s.name == "financial_statements"), None)
    if fs:
        result["fields"] = [
            f.model_dump()
            for f in extract_fields(pdf, fields, (fs.startPage, fs.endPage))
        ]
        result["statements"] = {
            s.name: [
                r.model_dump()
                for r in extract_statement(pdf, (s.startPage, s.endPage))
            ]
            for s in sections
            if s.name in STATEMENT_NAMES
        }
        if include_blocks:
            from .parser import parse_blocks  # lazy: needs Docling

            result["blocks"] = [
                b.model_dump()
                for b in parse_blocks(pdf, (fs.startPage, fs.endPage))
            ]

    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Parse a filing to JSON.")
    ap.add_argument("pdf", help="path to the PDF")
    ap.add_argument("-o", "--out", help="write JSON here (default: stdout)")
    ap.add_argument(
        "--fields",
        default=",".join(DEFAULT_FIELDS),
        help="comma-separated field keys to extract",
    )
    ap.add_argument(
        "--blocks",
        action="store_true",
        help="include Docling blocks for the Financial Statements range",
    )
    args = ap.parse_args()

    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    result = build_result(args.pdf, fields, args.blocks)
    text = json.dumps(result, indent=2, ensure_ascii=False)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
