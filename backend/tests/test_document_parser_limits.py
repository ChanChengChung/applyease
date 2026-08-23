from io import BytesIO
from zipfile import ZipFile

import pytest

from app.parsers import document_parser


def test_text_extraction_rejects_excessive_character_count():
    with pytest.raises(ValueError, match="extraction limit"):
        document_parser.extract_text("cv.txt", b"x" * 20, max_text_characters=10)


def test_docx_rejects_excessive_uncompressed_content_before_parsing():
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("word/document.xml", "x" * 100)

    with pytest.raises(ValueError, match="extracted-size limit"):
        document_parser.extract_text("cv.docx", payload.getvalue(), max_docx_uncompressed_bytes=20)


def test_pdf_rejects_page_and_extraction_limits(monkeypatch):
    class Page:
        def extract_text(self):
            return "abcdefghij"

    class Reader:
        pages = [Page(), Page()]

    monkeypatch.setattr(document_parser, "PdfReader", lambda _content: Reader())

    with pytest.raises(ValueError, match="page limit"):
        document_parser.extract_text("cv.pdf", b"pdf", max_pdf_pages=1)
    with pytest.raises(ValueError, match="extraction limit"):
        document_parser.extract_text("cv.pdf", b"pdf", max_pdf_pages=2, max_text_characters=10)
