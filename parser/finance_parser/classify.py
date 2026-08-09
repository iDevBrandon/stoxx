"""classify — what kind of document is this? Light and LLM-free: read the first
couple of pages' text with PyMuPDF and match a few patterns.

The docType picks which section taxonomy `split` uses, so this must run first.
"""

from __future__ import annotations

import re

import fitz  # PyMuPDF

_PATTERNS = [
    ("10-K", re.compile(r"FORM\s*10-?K", re.I)),
    ("10-Q", re.compile(r"FORM\s*10-?Q", re.I)),
    ("8-K", re.compile(r"FORM\s*8-?K", re.I)),
]


def classify_pdf(path: str) -> tuple[str, float]:
    doc = fitz.open(path)
    head = ""
    for i in range(min(2, doc.page_count)):
        head += doc[i].get_text("text") + "\n"
    doc.close()
    head = head[:6000]

    for name, pat in _PATTERNS:
        if pat.search(head):
            return name, 0.98
    if re.search(r"annual\s+report", head, re.I):
        return "annual_report", 0.8
    return "Unknown", 0.0


# docType → which taxonomy `split` should use.
def taxonomy_key(doc_type: str) -> str:
    if doc_type in ("10-K", "10-Q", "annual_report"):
        return doc_type
    return "default"
