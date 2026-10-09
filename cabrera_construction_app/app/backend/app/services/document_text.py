"""Converts an uploaded/pasted file into either plain text or raw PDF bytes
— shared by every AI extraction provider (Gemini, Anthropic, OpenAI), since
none of them natively understand .docx/.xlsx and all three handle PDF and
plain text their own way. Keeping this one place means docx/xlsx handling
(and its error messages) doesn't drift across three near-duplicate copies.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import docx
import openpyxl
import pillow_heif
from PIL import Image

# Registers HEIF/HEIC support into Pillow's Image.open — without this,
# Pillow has no idea how to decode the format iPhones save photos in by
# default, which is exactly what a phone camera uploads to Drive.
pillow_heif.register_heif_opener()

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Extension -> real MIME type, for an image whose content_type arrives as
# something generic (a raw upload, or a Drive file lacking useful metadata).
_IMAGE_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}

# Gemini accepts HEIC/HEIF natively, but Claude and OpenAI's vision APIs
# both reject any image media_type outside this set outright (a hard 400,
# not a "couldn't find anything" response) -- so a receipt photo in HEIC
# (the default format iPhones save in) only ever worked when Gemini
# happened to be the provider that handled it. Normalizing every image to
# one of these, once, before any provider sees it, makes the result the
# same no matter which provider ends up handling it.
_PROVIDER_SAFE_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class DocumentReadError(Exception):
    """A file claims to be .docx/.xlsx but isn't actually readable as one —
    see extract_docx_text/extract_xlsx_text. Each provider_service.py wraps
    this in its own extraction-error type; the message itself (which points
    the user at the paste-text fallback) stays identical everywhere."""


@dataclass
class TextPart:
    text: str


@dataclass
class PdfPart:
    data: bytes


@dataclass
class ImagePart:
    # A real photo (e.g. a receipt) needs real vision support, not the
    # "wrap it as a PdfPart and hope" treatment this file used to give any
    # non-text/docx/xlsx file — that mislabels a JPEG as application/pdf
    # once it reaches a provider, which doesn't parse. mime_type is kept
    # explicit (not re-derived from a filename) since every provider's
    # image block needs the real one.
    data: bytes
    mime_type: str


DocumentPart = TextPart | PdfPart | ImagePart


def extract_docx_text(docx_bytes: bytes) -> str:
    """Flattens a .docx's paragraphs and table cells into plain text, in
    document order. A file named "<something>.docx" isn't necessarily a
    real OOXML Word document — a legacy .doc saved years ago and just
    renamed, a Pages/Google Docs export with quirks, or a plain corrupted
    upload will make python-docx raise instead of returning text. That's a
    real, recurring case for a small contractor's informal notes files, so
    it's caught here and turned into a clear, actionable error rather than
    an uncaught 500 — the paste-text option on the Estimate Upload screen
    is the intended fallback when this happens."""
    try:
        document = docx.Document(io.BytesIO(docx_bytes))
    except Exception as exc:
        raise DocumentReadError(
            "This .docx file couldn't be read — it may not actually be a valid Word document "
            "(common if it was saved from an old .doc, or exported from another app). Open it, "
            "copy its text, and use \"Or paste the text directly\" instead."
        ) from exc
    parts: list[str] = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    text = "\n".join(parts)
    if not text.strip():
        raise DocumentReadError("This .docx file appears to have no readable text.")
    return text


def extract_xlsx_text(xlsx_bytes: bytes) -> str:
    """Flattens an .xlsx's sheets into plain text, row by row. A real
    "Project Scope and Payment Schedule" workbook is typically one sheet,
    one header row, and one row per payment phase (number, title,
    description, amount, due date) — exactly the shape a flattened
    "cell | cell | cell" text line preserves well enough to read as a
    table."""
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True, read_only=True)
    except Exception as exc:
        raise DocumentReadError(
            "This .xlsx file couldn't be read — it may be corrupted or not actually a valid "
            'Excel workbook. Open it, copy its text, and use "Or paste the text directly" instead.'
        ) from exc
    parts: list[str] = []
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                parts.append(" | ".join(cells))
    text = "\n".join(parts)
    if not text.strip():
        raise DocumentReadError("This .xlsx file appears to have no readable content.")
    return text


def _normalize_image_for_providers(data: bytes, mime_type: str) -> tuple[bytes, str]:
    """Decodes and re-encodes as JPEG anything not already in
    _PROVIDER_SAFE_IMAGE_TYPES -- HEIC/HEIF (iPhones), BMP, TIFF, or
    whatever else a phone or scanner produced. Already-safe formats pass
    through untouched (no needless re-encode on the common case)."""
    if mime_type in _PROVIDER_SAFE_IMAGE_TYPES:
        return data, mime_type
    try:
        image = Image.open(io.BytesIO(data))
        image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=92)
        return buffer.getvalue(), "image/jpeg"
    except Exception as exc:
        raise DocumentReadError(f"This photo ({mime_type}) couldn't be read — it may be corrupted or in an unsupported format.") from exc


def build_document_parts(files: list[tuple[bytes, str, str]]) -> list[DocumentPart]:
    """files: (bytes, filename, content_type) triples, same shape every
    caller already collects (an upload, a pasted-text pseudo-file, a Drive
    download). Returns one TextPart/PdfPart per file, in order — a provider
    turns each into its own native request format."""
    parts: list[DocumentPart] = []
    for file_bytes, filename, content_type in files:
        if content_type == "text/plain":
            parts.append(TextPart(text="Document contents:\n\n" + file_bytes.decode("utf-8")))
            continue
        is_docx = content_type == DOCX_MIME or filename.lower().endswith(".docx")
        is_xlsx = content_type == XLSX_MIME or filename.lower().endswith(".xlsx")
        image_ext = next((ext for ext in _IMAGE_EXTENSIONS if filename.lower().endswith(ext)), None)
        is_image = content_type.startswith("image/") or image_ext is not None
        if is_docx:
            parts.append(TextPart(text="Document contents:\n\n" + extract_docx_text(file_bytes)))
        elif is_xlsx:
            parts.append(TextPart(text="Spreadsheet contents:\n\n" + extract_xlsx_text(file_bytes)))
        elif is_image:
            mime = content_type if content_type.startswith("image/") else _IMAGE_EXTENSIONS[image_ext]
            data, mime = _normalize_image_for_providers(file_bytes, mime)
            parts.append(ImagePart(data=data, mime_type=mime))
        else:
            parts.append(PdfPart(data=file_bytes))
    return parts
