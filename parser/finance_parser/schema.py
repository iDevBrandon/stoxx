"""Output schema — mirrors what the Studio front-end expects, so the parser's
JSON drives the overlay boxes and section list with no reshaping on the client.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

# The four block types the Studio overlay knows how to color.
StudioType = Literal["Title", "Header", "Text", "Table"]


class BBox(BaseModel):
    # Normalized 0–1, top-left origin, relative to the page.
    x: float
    y: float
    w: float
    h: float


class Block(BaseModel):
    id: int
    type: StudioType
    page: int  # 1-based
    bbox: BBox
    text: str
    confidence: float = 0.95


class Section(BaseModel):
    name: str  # taxonomy key, e.g. "financial_statements"
    label: str  # human label, e.g. "Financial Statements"
    startPage: int  # 1-based, inclusive
    endPage: int  # 1-based, inclusive
    confidence: float


class ParseResult(BaseModel):
    docType: str  # "10-K" | "10-Q" | "8-K" | "annual_report" | "Unknown"
    docTypeConfidence: float
    numPages: int
    sections: list[Section]
    blocks: list[Block]
    # which page range /parse actually structured (None = whole document)
    parsedPages: Optional[list[int]] = None


class ExtractField(BaseModel):
    key: str
    label: str
    found: bool
    value: Optional[str] = None  # as printed, e.g. "$ 1,252,271"
    number: Optional[float] = None  # parsed numeric
    page: Optional[int] = None
    line: Optional[str] = None  # source line (citation)
    confidence: float = 0.0


class ExtractResult(BaseModel):
    docType: str
    section: str  # section name the values came from
    pages: list[int]  # [start, end] scanned
    fields: list[ExtractField]


class StatementRow(BaseModel):
    label: str
    values: list[str]  # figures as printed, left→right (current period first)
    page: int


class StatementResult(BaseModel):
    name: str  # e.g. "balance_sheet"
    label: str  # e.g. "Balance Sheet"
    pages: list[int]  # [start, end]
    rows: list[StatementRow]
