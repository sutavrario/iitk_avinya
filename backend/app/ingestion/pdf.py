"""PDF/image text extraction: embedded text layer first (pypdfium2), OCR for pages without one."""

import io
from typing import Literal

import pypdfium2 as pdfium
from PIL import Image, UnidentifiedImageError

from app.ingestion.errors import IngestionError
from app.ingestion.models import PageText
from app.ingestion.ocr import OcrProvider

MAX_PDF_PAGES = 30
MIN_TEXT_CHARS = 25  # fewer characters than this ⇒ treat the page as scanned
OCR_SCALE = 300 / 72  # render at 300 DPI
MAX_IMAGE_PIXELS = 40_000_000

PdfTextStrategy = Literal["auto", "ocr"]


def extract_pdf_pages(
    content: bytes, ocr: OcrProvider, strategy: PdfTextStrategy = "auto"
) -> list[PageText]:
    try:
        doc = pdfium.PdfDocument(content)
    except pdfium.PdfiumError as exc:
        message = str(exc).lower()
        if "password" in message:
            raise IngestionError(
                "password_protected",
                "This PDF is password-protected. Remove the password and upload it again.",
            ) from exc
        raise IngestionError("malformed_file", "This PDF is damaged or incomplete.") from exc

    try:
        if len(doc) == 0:
            raise IngestionError("empty_file", "This PDF has no pages.")
        if len(doc) > MAX_PDF_PAGES:
            raise IngestionError("too_many_pages", f"PDFs can have at most {MAX_PDF_PAGES} pages.")
        pages: list[PageText] = []
        for index in range(len(doc)):
            page = doc[index]
            try:
                text = ""
                if strategy == "auto":
                    textpage = page.get_textpage()
                    text = textpage.get_text_range().replace("\r\n", "\n").replace("\r", "\n")
                    textpage.close()
                if len(text.strip()) >= MIN_TEXT_CHARS:
                    pages.append(PageText(index + 1, text, "text_layer", 1.0))
                    continue
                image = page.render(scale=OCR_SCALE).to_pil()
                result = ocr.recognize(image)
                pages.append(PageText(index + 1, result.text, "ocr", result.confidence))
            finally:
                page.close()
        return pages
    finally:
        doc.close()


def extract_image_text(content: bytes, ocr: OcrProvider) -> list[PageText]:
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS  # decompression-bomb guard
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.load()
            image = img.copy()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise IngestionError(
            "malformed_file", "This image is damaged or too large to read."
        ) from exc
    result = ocr.recognize(image)
    return [PageText(1, result.text, "ocr", result.confidence)]
