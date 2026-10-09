"""build_document_parts' image handling — a receipt photo must become a
real ImagePart (correct mime_type), not silently get mislabeled as a
PdfPart the way any non-text/docx/xlsx file used to before image support
existed."""

from app.services.document_text import ImagePart, PdfPart, TextPart, build_document_parts


def test_jpg_filename_becomes_image_part_with_correct_mime():
    parts = build_document_parts([(b"fake-jpeg-bytes", "receipt.jpg", "application/octet-stream")])
    assert len(parts) == 1
    assert isinstance(parts[0], ImagePart)
    assert parts[0].mime_type == "image/jpeg"
    assert parts[0].data == b"fake-jpeg-bytes"


def test_png_content_type_becomes_image_part_even_with_generic_filename():
    parts = build_document_parts([(b"fake-png-bytes", "IMG_1234", "image/png")])
    assert len(parts) == 1
    assert isinstance(parts[0], ImagePart)
    assert parts[0].mime_type == "image/png"


def test_pdf_still_becomes_pdf_part_not_image():
    parts = build_document_parts([(b"%PDF-fake", "estimate.pdf", "application/pdf")])
    assert len(parts) == 1
    assert isinstance(parts[0], PdfPart)


def test_plain_text_still_becomes_text_part():
    parts = build_document_parts([(b"hello", "notes.txt", "text/plain")])
    assert len(parts) == 1
    assert isinstance(parts[0], TextPart)
