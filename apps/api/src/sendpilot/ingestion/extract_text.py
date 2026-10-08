"""Per-format text/table extraction (PRD §7.2).

Dispatches on MIME type and returns a normalized :class:`DocumentText`: the full
text plus structural hints (DataFrames for tabular, sections for narrative) used
by the classifier and the chunker. OCR is used only when a PDF/image yields
little or no embedded text.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pandas as pd

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass
class DocumentText:
    text: str
    kind: str  # 'table' | 'document'
    tables: list[pd.DataFrame] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)


def extract_document_text(data: bytes, mime: str) -> DocumentText:
    if mime in ("text/csv",):
        df = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)
        return DocumentText(text=df.to_csv(index=False), kind="table", tables=[df])

    if mime == XLSX_MIME:
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, dtype=str)
        frames = [s.fillna("") for s in sheets.values()]
        text = "\n\n".join(f.to_csv(index=False) for f in frames)
        return DocumentText(text=text, kind="table", tables=frames)

    if mime == DOCX_MIME:
        import docx

        d = docx.Document(io.BytesIO(data))
        paras = [p.text for p in d.paragraphs]
        return DocumentText(text="\n".join(paras), kind="document", sections=paras)

    if mime == "application/pdf":
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [pg.extract_text() or "" for pg in pdf.pages]
        text = "\n\n".join(pages)
        if len(text.strip()) < 40 * max(1, len(pages)):  # likely scanned
            text = _ocr_pdf(data)
        return DocumentText(text=text, kind="document", sections=pages)

    if mime in ("image/png", "image/jpeg"):
        return DocumentText(text=_ocr_image(data), kind="document")

    if mime == "text/html":
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(data, "html.parser")
        return DocumentText(text=soup.get_text("\n"), kind="document")

    # text/plain, text/markdown
    return DocumentText(text=data.decode("utf-8", "replace"), kind="document")


def _ocr_image(data: bytes) -> str:
    import pytesseract
    from PIL import Image

    return pytesseract.image_to_string(Image.open(io.BytesIO(data)))


def _ocr_pdf(data: bytes) -> str:
    import pytesseract
    from pdf2image import convert_from_bytes

    return "\n\n".join(pytesseract.image_to_string(img) for img in convert_from_bytes(data))
