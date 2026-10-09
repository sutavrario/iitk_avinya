"""OCR provider interface. Tesseract is the built-in, free implementation."""

import shutil
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from app.ingestion.errors import IngestionError


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float  # 0..1, mean word confidence


class OcrProvider(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def recognize(self, image: Image.Image) -> OcrResult: ...


class UnavailableOcrProvider:
    """Used when OCR is disabled or not installed. Scanned pages fail with a clear message."""

    name = "none"

    def __init__(self, reason: str = "OCR isn't configured on the server.") -> None:
        self.reason = reason

    def is_available(self) -> bool:
        return False

    def recognize(self, image: Image.Image) -> OcrResult:
        raise IngestionError(
            "ocr_unavailable",
            f"This looks like a scanned page or photo, but {self.reason[0].lower()}{self.reason[1:]} "
            "Upload a digital PDF or spreadsheet instead, or ask the administrator to enable OCR.",
        )


class TesseractOcrProvider:
    """Local Tesseract via pytesseract. Needs the `tesseract` binary (e.g. `brew install tesseract`)."""

    name = "tesseract"

    def __init__(
        self, languages: str = "eng", command: str | None = None, timeout_seconds: int = 60
    ) -> None:
        self.languages = languages
        self.command = command
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return bool(self.command or shutil.which("tesseract"))

    def recognize(self, image: Image.Image) -> OcrResult:
        import pytesseract

        if self.command:
            pytesseract.pytesseract.tesseract_cmd = self.command
        gray = image.convert("L")
        try:
            data = pytesseract.image_to_data(
                gray,
                lang=self.languages,
                config="--psm 6",  # assume a uniform block of text; works well for invoices
                output_type=pytesseract.Output.DICT,
                timeout=self.timeout_seconds,
            )
        except RuntimeError as exc:  # pytesseract raises RuntimeError on timeout
            raise IngestionError(
                "ocr_timeout", "Reading this page took too long.", retryable=True
            ) from exc
        except pytesseract.TesseractNotFoundError as exc:
            raise IngestionError(
                "ocr_unavailable", "OCR is enabled but Tesseract isn't installed on the server."
            ) from exc
        except pytesseract.TesseractError as exc:
            raise IngestionError("ocr_failed", "OCR couldn't read this page.") from exc

        lines: dict[tuple[int, int, int], list[str]] = {}
        confidences: list[float] = []
        for i, word in enumerate(data["text"]):
            word = (word or "").strip()
            conf = float(data["conf"][i])
            if not word or conf < 0:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(word)
            confidences.append(conf)
        text = "\n".join(" ".join(words) for _, words in sorted(lines.items()))
        mean = sum(confidences) / len(confidences) / 100 if confidences else 0.0
        return OcrResult(text=text, confidence=round(mean, 3))


def build_ocr_provider(
    provider: str, languages: str, command: str | None, timeout_seconds: int
) -> OcrProvider:
    if provider == "tesseract":
        tess = TesseractOcrProvider(languages, command, timeout_seconds)
        if tess.is_available():
            return tess
        return UnavailableOcrProvider("Tesseract isn't installed on the server.")
    return UnavailableOcrProvider()
