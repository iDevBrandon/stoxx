"""Local FastAPI server. Run:

    python -m uvicorn finance_parser.main:app --reload --port 8000

Endpoints:
  GET  /health           → {"ok": true}
  POST /split  (file)    → classify + split only (fast, no Docling): docType +
                           section page ranges. Great for a section picker.
  POST /parse  (file,    → classify + split, then Docling-parse ONE section's
               section?)    page range (defaults to Financial Statements).

CORS is open to the Next dev server so Studio can call it from the browser.
`parser` (Docling/torch) is imported lazily inside /parse so /split stays light.
"""

from __future__ import annotations

import os
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .classify import classify_pdf, taxonomy_key
from .schema import ExtractResult, ParseResult, Section, StatementResult
from .split import page_count, split_pdf

app = FastAPI(title="Oxinion finance-parser", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "https://finance.oxinion.com",
        "https://www.finance.oxinion.com",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB — protects the small free instance


async def _save_upload(file: UploadFile) -> str:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a .pdf file")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large — max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        return tmp.name


def _classify_and_split(path: str) -> tuple[str, float, int, list[Section]]:
    doc_type, conf = classify_pdf(path)
    total = page_count(path)
    sections = split_pdf(path, taxonomy_key(doc_type))
    return doc_type, conf, total, sections


def _pick_section(
    sections: list[Section], requested: str | None
) -> Section | None:
    if requested:
        for s in sections:
            if s.name == requested:
                return s
    for s in sections:
        if s.name == "financial_statements":
            return s
    return None


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/split", response_model=ParseResult)
async def split(file: UploadFile = File(...)) -> ParseResult:
    path = await _save_upload(file)
    try:
        doc_type, conf, total, sections = _classify_and_split(path)
        return ParseResult(
            docType=doc_type,
            docTypeConfidence=conf,
            numPages=total,
            sections=sections,
            blocks=[],
            parsedPages=None,
        )
    finally:
        if os.path.exists(path):
            os.unlink(path)


@app.post("/parse", response_model=ParseResult)
async def parse(
    file: UploadFile = File(...),
    section: str | None = Form(None),
) -> ParseResult:
    path = await _save_upload(file)
    try:
        doc_type, conf, total, sections = _classify_and_split(path)

        # Lazy import so /split never pays the Docling/torch import cost.
        from .parser import parse_blocks

        target = _pick_section(sections, section)
        if target:
            blocks = parse_blocks(path, pages=(target.startPage, target.endPage))
            parsed = [target.startPage, target.endPage]
        else:
            blocks = parse_blocks(path)
            parsed = [1, total]

        return ParseResult(
            docType=doc_type,
            docTypeConfidence=conf,
            numPages=total,
            sections=sections,
            blocks=blocks,
            parsedPages=parsed,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Parse failed: {exc}") from exc
    finally:
        if os.path.exists(path):
            os.unlink(path)


@app.post("/extract", response_model=ExtractResult)
async def extract(
    file: UploadFile = File(...),
    fields: str | None = Form(None),  # comma-separated field keys
    section: str | None = Form(None),
) -> ExtractResult:
    path = await _save_upload(file)
    try:
        doc_type, _conf, total, sections = _classify_and_split(path)
        target = _pick_section(sections, section)
        pages = (target.startPage, target.endPage) if target else (1, total)

        from .extract import DEFAULT_FIELDS, extract_fields

        keys = (
            [f.strip() for f in fields.split(",") if f.strip()]
            if fields
            else DEFAULT_FIELDS
        )
        got = extract_fields(path, keys, pages)

        return ExtractResult(
            docType=doc_type,
            section=target.name if target else "document",
            pages=[pages[0], pages[1]],
            fields=got,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extract failed: {exc}") from exc
    finally:
        if os.path.exists(path):
            os.unlink(path)


@app.post("/statement", response_model=StatementResult)
async def statement(
    file: UploadFile = File(...),
    name: str = Form(...),  # section name, e.g. "balance_sheet"
) -> StatementResult:
    path = await _save_upload(file)
    try:
        _dt, _conf, _total, sections = _classify_and_split(path)
        target = next((s for s in sections if s.name == name), None)
        if target is None:
            raise HTTPException(status_code=404, detail=f"Section '{name}' not found")

        from .extract import extract_statement

        rows = extract_statement(path, (target.startPage, target.endPage))
        return StatementResult(
            name=target.name,
            label=target.label,
            pages=[target.startPage, target.endPage],
            rows=rows,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Statement failed: {exc}") from exc
    finally:
        if os.path.exists(path):
            os.unlink(path)
