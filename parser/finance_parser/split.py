"""split — find where each meaningful section lives (page ranges). No LLM, no
heavy ML: read text with PyMuPDF, match headings against a docType-specific
taxonomy, and turn heading positions into ranges.

This is deliberately cheap so it can run over a 250-page filing in seconds. Its
main job is to let `parse` run the expensive Docling pass on only the pages that
matter (e.g. Financial Statements) instead of the whole document.
"""

from __future__ import annotations

import re

import fitz  # PyMuPDF

from .schema import Section

# Ordered by how they usually appear. Patterns are matched against normalized
# (lowercased, whitespace-collapsed) line text.
SECTION_PATTERNS: dict[str, dict[str, list[str]]] = {
    "10-K": {
        "business": ["item 1. business", "item 1 business"],
        "risk_factors": ["item 1a. risk factors", "item 1a risk factors"],
        "properties": ["item 2. properties"],
        "legal": ["item 3. legal proceedings"],
        "mdna": [
            "item 7. managements discussion",
            "managements discussion and analysis",
        ],
        "market_risk": ["item 7a. quantitative and qualitative"],
        "financial_statements": [
            "item 8. financial statements",
            "consolidated financial statements",
            "report of independent registered public accounting firm",
        ],
        "notes": [
            "notes to consolidated financial statements",
            "notes to the consolidated financial statements",
        ],
    },
    "10-Q": {
        "financial_statements": [
            "item 1. financial statements",
            "consolidated balance sheets",
            "consolidated balance sheet",
            "consolidated statements of earnings",
            "consolidated statement of earnings",
            "consolidated statements of operations",
            "consolidated statement of operations",
            "consolidated statements of income",
            "consolidated statement of income",
        ],
        "mdna": [
            "item 2. managements discussion",
            "managements discussion and analysis",
        ],
        "market_risk": ["item 3. quantitative and qualitative"],
        "controls": ["item 4. controls and procedures"],
        "risk_factors": ["item 1a. risk factors"],
        "legal": ["item 1. legal proceedings"],
    },
    "annual_report": {
        "business": ["our business", "business overview", "company profile"],
        "risk_factors": ["risk factors", "risk management"],
        "mdna": [
            "management report",
            "operating and financial review",
            "managements discussion",
        ],
        "financial_statements": [
            "consolidated statement of profit or loss",
            "consolidated income statement",
            "consolidated statement of financial position",
            "consolidated balance sheet",
            "consolidated statements of operations",
            "consolidated financial statements",
        ],
        "notes": [
            "notes to the consolidated financial statements",
            "notes to the financial statements",
        ],
    },
    "default": {
        "financial_statements": [
            "consolidated financial statements",
            "consolidated balance sheet",
            "consolidated statements of operations",
            "consolidated statement of profit or loss",
            "income statement",
            "balance sheet",
        ],
        "notes": ["notes to the financial statements"],
    },
}

# The individual financial statements, detected WITHIN the financial_statements
# section so each can be selected/parsed on its own (the "big 3" + friends).
STATEMENT_PATTERNS: dict[str, list[str]] = {
    "balance_sheet": [
        "consolidated balance sheet",
        "consolidated balance sheets",
        "consolidated statement of financial position",
        "consolidated statements of financial position",
    ],
    "income_statement": [
        "consolidated statement of earnings",
        "consolidated statements of earnings",
        "consolidated statement of operations",
        "consolidated statements of operations",
        "consolidated income statement",
        "consolidated statements of income",
        "consolidated statement of income",
        "consolidated statement of profit or loss",
    ],
    "comprehensive_income": [
        "consolidated statement of comprehensive income",
        "consolidated statements of comprehensive income",
    ],
    "equity_changes": [
        "consolidated statement of changes in equity",
        "consolidated statements of changes in equity",
        "consolidated statement of changes in shareholders",
        "consolidated statements of changes in shareholders",
        "consolidated statement of stockholders equity",
        "consolidated statements of stockholders equity",
        "consolidated statement of shareholders",
        "consolidated statements of shareholders",
        "consolidated statement of equity",
        "consolidated statements of equity",
        "changes in shareholders equity",
    ],
    "cash_flow": [
        "consolidated statement of cash flows",
        "consolidated statements of cash flows",
    ],
    # Bounds cash_flow: Notes start right after the statements.
    "notes": [
        "notes to consolidated financial statements",
        "notes to the consolidated financial statements",
        "notes to financial statements",
        "notes to the financial statements",
    ],
}

LABELS: dict[str, str] = {
    "cover": "Cover / General",
    "balance_sheet": "Balance Sheet",
    "income_statement": "Income Statement",
    "comprehensive_income": "Comprehensive Income",
    "equity_changes": "Changes in Equity",
    "cash_flow": "Cash Flow Statement",
    "business": "Business",
    "risk_factors": "Risk Factors",
    "properties": "Properties",
    "legal": "Legal Proceedings",
    "mdna": "MD&A",
    "market_risk": "Market Risk",
    "financial_statements": "Financial Statements",
    "notes": "Notes",
    "controls": "Controls & Procedures",
    "document": "Whole document",
}


def _norm(s: str) -> str:
    # Drop non-ASCII (curly/'smart' or font-mangled apostrophes like the glyph
    # some filers emit for "management's") so apostrophes just disappear:
    # "management's" / "managementᓼs" → "managements". Patterns are written
    # apostrophe-free to match.
    # Keep only printable ASCII — drops smart quotes (≥0x80) AND control-char
    # apostrophes some filers emit (e.g. Palantir uses 0x11 for "management's").
    s = re.sub(r"[^\x20-\x7e]", "", s)
    s = re.sub(r"\s+", " ", s).strip().strip(".:").strip().lower()
    # 10-Q statement titles carry noise words — strip them so "condensed
    # consolidated balance sheets" matches "consolidated balance sheets".
    s = re.sub(r"\b(condensed|unaudited)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def page_count(path: str) -> int:
    doc = fitz.open(path)
    n = doc.page_count
    doc.close()
    return n


def _is_toc_line(line: str, n: int) -> bool:
    """A table-of-contents entry ends with a page reference, e.g.
    'item 1. financial statements 2' or '... risk factors 46'. Real section
    headings on their own page don't. We treat a trailing number ≤ page count
    as a page ref (a year like 2026 is > n, so it's kept)."""
    m = re.search(r"(\d{1,4})\s*$", line)
    if not m:
        return False
    return 1 <= int(m.group(1)) <= n


def _match(lines: list[str], patterns: list[str], n: int) -> float | None:
    """Best score for any pattern against any non-TOC line on the page."""
    best: float | None = None
    for line in lines:
        if _is_toc_line(line, n):
            continue
        for p in patterns:
            if line.startswith(p):
                return 0.95  # a heading line that starts with the pattern
            if p in line and len(line) <= len(p) + 60:
                best = max(best or 0, 0.82)
    return best


def _starts_with(lines: list[str], patterns: list[str]) -> bool:
    """Strict: a line must START with a pattern AND be roughly just the title
    (short). This skips the recurring footer 'See accompanying Notes …' and,
    crucially, prose mentions inside the Notes like 'Consolidated Statement of
    Income for the period …' that would otherwise mislocate a statement."""
    for line in lines:
        for p in patterns:
            if line.startswith(p) and len(line) <= len(p) + 15:
                return True
    return False


def _find_statements(
    page_lines: list[list[str]], fs_start: int, fs_end: int, n: int
) -> list[Section]:
    """Within the Financial Statements range, locate each individual statement
    (balance sheet, income statement, cash flow, …) and turn them into ranges."""
    found: dict[str, tuple[int, float]] = {}
    hi = min(fs_end, len(page_lines))
    for i in range(fs_start - 1, hi):
        lines = page_lines[i]
        for name, pats in STATEMENT_PATTERNS.items():
            if name in found:
                continue
            if _starts_with(lines, pats):
                found[name] = (i + 1, 0.95)

    if not found:
        return []

    ordered = sorted(found.items(), key=lambda kv: kv[1][0])
    out: list[Section] = []
    for idx, (name, (start, score)) in enumerate(ordered):
        end = ordered[idx + 1][1][0] - 1 if idx + 1 < len(ordered) else fs_end
        if end < start:
            end = start
        out.append(
            Section(
                name=name,
                label=LABELS.get(name, name),
                startPage=start,
                endPage=end,
                confidence=round(score, 2),
            )
        )
    return out


def split_pdf(path: str, taxonomy: str) -> list[Section]:
    patterns = SECTION_PATTERNS.get(taxonomy, SECTION_PATTERNS["default"])

    doc = fitz.open(path)
    n = doc.page_count
    page_lines: list[list[str]] = []
    for i in range(n):
        text = doc[i].get_text("text")
        page_lines.append([_norm(ln) for ln in text.splitlines() if ln.strip()])
    doc.close()

    # A table-of-contents page lists many sections at once and must be skipped,
    # or its entries get mistaken for real boundaries. Two signals:
    #  (1) the page literally says "table of contents" near the top, or
    #  (2) 3+ distinct sections match on one page.
    # (Some filings split "Item N." and the title onto separate TOC lines, so
    #  signal 1 is the reliable catch-all.)
    def distinct_hits(lines: list[str]) -> int:
        return sum(
            1 for pats in patterns.values() if _match(lines, pats, n) is not None
        )

    def is_toc(lines: list[str]) -> bool:
        # Real TOC pages have many bare page-reference lines (just a number ≤ n).
        # ("Table of Contents" itself is often a running header on every page,
        #  so it isn't a usable signal.)
        refs = sum(1 for ln in lines if ln.isdigit() and 1 <= int(ln) <= n)
        if refs >= 5:
            return True
        return distinct_hits(lines) >= 3

    toc_pages = {i for i, lines in enumerate(page_lines) if is_toc(lines)}

    # First real (non-TOC) page where each section appears.
    found: dict[str, tuple[int, float]] = {}
    for i, lines in enumerate(page_lines):
        if i in toc_pages:
            continue
        for name, pats in patterns.items():
            if name in found:
                continue
            score = _match(lines, pats, n)
            if score is not None:
                found[name] = (i + 1, score)  # 1-based page

    if not found:
        # Nothing matched — treat the whole doc as one section so parse still runs.
        return [
            Section(
                name="document",
                label=LABELS["document"],
                startPage=1,
                endPage=n,
                confidence=0.3,
            )
        ]

    ordered = sorted(found.items(), key=lambda kv: kv[1][0])
    sections: list[Section] = []

    first_page = ordered[0][1][0]
    if first_page > 1:
        sections.append(
            Section(
                name="cover",
                label=LABELS["cover"],
                startPage=1,
                endPage=first_page - 1,
                confidence=0.9,
            )
        )

    for idx, (name, (start, score)) in enumerate(ordered):
        end = ordered[idx + 1][1][0] - 1 if idx + 1 < len(ordered) else n
        if end < start:
            end = start
        sections.append(
            Section(
                name=name,
                label=LABELS.get(name, name),
                startPage=start,
                endPage=end,
                confidence=round(score, 2),
            )
        )

    # Within Financial Statements, break out the individual statements (big 3 +
    # comprehensive income / equity) and splice them in right after FS.
    fs = next((s for s in sections if s.name == "financial_statements"), None)
    if fs:
        stmts = _find_statements(page_lines, fs.startPage, fs.endPage, n)
        if stmts:
            idx = sections.index(fs)
            sections[idx + 1 : idx + 1] = stmts

    return sections
