from pathlib import Path
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from docx import Document
from pypdf import PdfReader


def _bounded_text(parts: list[str], maximum: int) -> str:
    text = "\n".join(parts)
    if len(text) > maximum:
        raise ValueError("Document text exceeds the allowed extraction limit")
    return text


def extract_text(
    filename: str,
    content: bytes,
    *,
    max_pdf_pages: int = 50,
    max_text_characters: int = 200_000,
    max_docx_uncompressed_bytes: int = 25 * 1024 * 1024,
) -> str:
    suffix = Path(filename).suffix.lower()

    if not content:

        raise ValueError("The uploaded document is empty")

    if suffix == ".pdf":
        reader = PdfReader(BytesIO(content))

        if len(reader.pages) > max_pdf_pages:
            raise ValueError("PDF exceeds the allowed page limit")
        parts: list[str] = []
        size = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            size += len(page_text)
            if size > max_text_characters:
                raise ValueError("Document text exceeds the allowed extraction limit")
            parts.append(page_text)
        text = "\n".join(parts)

        if not text.strip():

            raise ValueError("This PDF contains no selectable text; OCR is not enabled yet")

        return text

    if suffix == ".docx":
        try:
            with ZipFile(BytesIO(content)) as archive:
                uncompressed = sum(item.file_size for item in archive.infolist())
                if uncompressed > max_docx_uncompressed_bytes:
                    raise ValueError("DOCX exceeds the allowed extracted-size limit")
        except BadZipFile as exc:
            raise ValueError("Invalid DOCX file") from exc
        text = _bounded_text(
            [paragraph.text for paragraph in Document(BytesIO(content)).paragraphs],
            max_text_characters,
        )

        if not text.strip():

            raise ValueError("This DOCX contains no readable text")

        return text

    if suffix in {".txt", ".md"}:
        text = content.decode("utf-8", errors="ignore")

        if len(text) > max_text_characters:
            raise ValueError("Document text exceeds the allowed extraction limit")

        if not text.strip():

            raise ValueError("The uploaded document is empty")

        return text

    raise ValueError("Only PDF, DOCX, TXT and MD files are supported")
