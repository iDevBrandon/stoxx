"""parse — dual engine, both alive in one file:

  • Docling  — best layout/table quality (needs docling+torch, ~2GB RAM). Used
               on beefy hosts / GitHub Actions.
  • PyMuPDF  — light, fits 512MB free hosts (Render free). Table finder + font
               heuristics.

Engine is auto-selected: Docling if importable, else PyMuPDF. Override with the
PARSER_ENGINE env var ("docling" or "pymupdf"). bbox is normalized 0–1, top-left.
Both paths return the same Block schema, so callers don't care which ran.
"""

from __future__ import annotations

import os
from typing import Optional

import fitz  # PyMuPDF (always available)

from .schema import BBox, Block


def _engine() -> str:
    forced = os.getenv("PARSER_ENGINE", "").lower().strip()
    if forced in ("docling", "pymupdf"):
        return forced
    try:
        import docling  # noqa: F401

        return "docling"
    except Exception:
        return "pymupdf"


def parse_blocks(
    path: str, pages: Optional[tuple[int, int]] = None
) -> list[Block]:
    if _engine() == "docling":
        try:
            return _parse_docling(path, pages)
        except Exception:
            # If Docling blows up (memory, model download, version drift),
            # still return something usable.
            return _parse_pymupdf(path, pages)
    return _parse_pymupdf(path, pages)


# ───────────────────────── PyMuPDF engine ─────────────────────────
def _norm_bbox(r: "fitz.Rect", pw: float, ph: float) -> BBox:
    def c(v: float) -> float:
        return max(0.0, min(1.0, v))

    return BBox(
        x=round(c(r.x0 / pw), 4),
        y=round(c(r.y0 / ph), 4),
        w=round(c((r.x1 - r.x0) / pw), 4),
        h=round(c((r.y1 - r.y0) / ph), 4),
    )


def _type_by_size(size: float, med: float) -> str:
    if size >= med * 1.45:
        return "Title"
    if size >= med * 1.15:
        return "Header"
    return "Text"


def _parse_pymupdf(
    path: str, pages: Optional[tuple[int, int]] = None
) -> list[Block]:
    doc = fitz.open(path)
    start = pages[0] if pages else 1
    end = min(pages[1], doc.page_count) if pages else doc.page_count
    rows: list[tuple[int, float, float, Block]] = []

    for pno in range(start, end + 1):
        page = doc[pno - 1]
        pw, ph = page.rect.width, page.rect.height
        if pw <= 0 or ph <= 0:
            continue

        table_rects: list[fitz.Rect] = []
        try:
            for t in page.find_tables().tables:
                tr = fitz.Rect(t.bbox)
                table_rects.append(tr)
                try:
                    txt = t.to_markdown()
                except Exception:
                    txt = page.get_textbox(tr)
                rows.append(
                    (
                        pno,
                        tr.y0,
                        tr.x0,
                        Block(
                            id=0,
                            type="Table",
                            page=pno,
                            bbox=_norm_bbox(tr, pw, ph),
                            text=(txt or "").strip()[:4000],
                            confidence=0.8,
                        ),
                    )
                )
        except Exception:
            table_rects = []

        d = page.get_text("dict")
        sizes = [
            s["size"]
            for b in d["blocks"]
            for line in b.get("lines", [])
            for s in line.get("spans", [])
        ]
        med = sorted(sizes)[len(sizes) // 2] if sizes else 10.0

        for b in d["blocks"]:
            if b.get("type", 0) != 0:
                continue
            r = fitz.Rect(b["bbox"])
            cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
            if any(
                tr.x0 <= cx <= tr.x1 and tr.y0 <= cy <= tr.y1 for tr in table_rects
            ):
                continue
            text = ""
            max_size = 0.0
            for line in b.get("lines", []):
                for s in line.get("spans", []):
                    text += s["text"]
                    max_size = max(max_size, s["size"])
                text += "\n"
            text = text.strip()
            if not text:
                continue
            rows.append(
                (
                    pno,
                    r.y0,
                    r.x0,
                    Block(
                        id=0,
                        type=_type_by_size(max_size, med),  # type: ignore[arg-type]
                        page=pno,
                        bbox=_norm_bbox(r, pw, ph),
                        text=text[:4000],
                        confidence=0.7,
                    ),
                )
            )

    doc.close()
    rows.sort(key=lambda o: (o[0], round(o[1], 1), o[2]))
    blocks = [o[3] for o in rows]
    for i, b in enumerate(blocks, 1):
        b.id = i
    return blocks


# ───────────────────────── Docling engine ─────────────────────────
_CONVERTER = None  # cached DocumentConverter (heavy)


def _studio_type_from_label(label) -> str:
    name = str(getattr(label, "value", label) or "").lower()
    if "title" in name:
        return "Title"
    if "header" in name:  # section_header / page_header
        return "Header"
    if "table" in name:
        return "Table"
    return "Text"


def _docling_item_text(item, doc) -> str:
    txt = getattr(item, "text", None)
    if txt:
        return str(txt).strip()
    md = getattr(item, "export_to_markdown", None)
    if md is not None:
        for call in (lambda: md(doc), lambda: md()):
            try:
                return str(call()).strip()
            except Exception:
                continue
    df = getattr(item, "export_to_dataframe", None)
    if df is not None:
        try:
            return df().to_csv(index=False).strip()
        except Exception:
            pass
    return ""


def _parse_docling(
    path: str, pages: Optional[tuple[int, int]] = None
) -> list[Block]:
    global _CONVERTER
    from docling.document_converter import DocumentConverter

    if _CONVERTER is None:
        _CONVERTER = DocumentConverter()

    doc = None
    if pages:
        try:
            doc = _CONVERTER.convert(
                path, page_range=(pages[0], pages[1])
            ).document
        except TypeError:
            doc = None
    if doc is None:
        doc = _CONVERTER.convert(path).document

    pages_map = getattr(doc, "pages", {}) or {}
    blocks: list[Block] = []
    bid = 0

    for item, _level in doc.iterate_items():
        prov = getattr(item, "prov", None)
        if not prov:
            continue
        p = prov[0]
        page_no = getattr(p, "page_no", None)
        bbox_raw = getattr(p, "bbox", None)
        if page_no is None or bbox_raw is None:
            continue
        if pages and not (pages[0] <= page_no <= pages[1]):
            continue

        page = pages_map.get(page_no)
        size = getattr(page, "size", None) if page else None
        if size is None:
            continue
        pw, ph = float(size.width), float(size.height)
        if pw <= 0 or ph <= 0:
            continue

        try:
            b = bbox_raw.to_top_left_origin(page_height=ph)
        except Exception:
            b = bbox_raw

        def clamp(v: float) -> float:
            return max(0.0, min(1.0, v))

        bid += 1
        blocks.append(
            Block(
                id=bid,
                type=_studio_type_from_label(getattr(item, "label", None)),  # type: ignore[arg-type]
                page=page_no,
                bbox=BBox(
                    x=round(clamp(b.l / pw), 4),
                    y=round(clamp(b.t / ph), 4),
                    w=round(clamp((b.r - b.l) / pw), 4),
                    h=round(clamp((b.b - b.t) / ph), 4),
                ),
                text=_docling_item_text(item, doc),
                confidence=0.95,
            )
        )

    return blocks
