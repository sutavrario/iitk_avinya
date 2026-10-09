"""Validation and storage of original uploaded documents. Extraction is not implemented yet."""

import re
import unicodedata
from dataclasses import dataclass
from typing import BinaryIO

from app.core.errors import AppError, PayloadTooLargeError, UnsupportedMediaTypeError


@dataclass(frozen=True)
class FileType:
    kind: str
    content_type: str
    signatures: tuple[bytes, ...]  # empty = text file, checked separately


# Content type is decided by us from extension + magic bytes, never by the client's header.
ALLOWED: dict[str, FileType] = {
    ".pdf": FileType("pdf", "application/pdf", (b"%PDF-",)),
    ".png": FileType("image", "image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": FileType("image", "image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": FileType("image", "image/jpeg", (b"\xff\xd8\xff",)),
    ".xlsx": FileType(
        "spreadsheet",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        (b"PK\x03\x04",),
    ),
    ".xls": FileType(
        "spreadsheet", "application/vnd.ms-excel", (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)
    ),
    ".csv": FileType("spreadsheet", "text/csv", ()),
}


@dataclass(frozen=True)
class ValidatedUpload:
    original_name: str
    extension: str
    file_type: FileType
    content: bytes


def safe_display_name(name: str | None) -> str:
    """Strip paths/control chars. Display-only: never used as a storage path."""
    base = (name or "upload").replace("\\", "/").rsplit("/", 1)[-1]
    base = unicodedata.normalize("NFKC", base)
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip(" .")
    return base[:120] or "upload"


def read_limited(stream: BinaryIO, max_bytes: int) -> bytes:
    data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise PayloadTooLargeError(
            f"Files must be under {max_bytes // (1024 * 1024)} MB.", code="file_too_large"
        )
    return data


def validate_upload(filename: str | None, content: bytes) -> ValidatedUpload:
    name = safe_display_name(filename)
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    file_type = ALLOWED.get(ext)
    if file_type is None:
        raise UnsupportedMediaTypeError(
            "This file type isn't supported. Use Excel, CSV, PDF or a photo (JPG/PNG).",
            code="unsupported_file_type",
        )
    if not content:
        raise AppError("The file is empty.", code="empty_file")
    if file_type.signatures:
        if not any(content.startswith(sig) for sig in file_type.signatures):
            raise UnsupportedMediaTypeError(
                f"The file's contents don't look like a {ext} file.", code="file_content_mismatch"
            )
    elif b"\x00" in content[:8192]:
        raise UnsupportedMediaTypeError(
            "This doesn't look like a text CSV file.", code="file_content_mismatch"
        )
    return ValidatedUpload(original_name=name, extension=ext, file_type=file_type, content=content)


def storage_path(business_id: str, document_id: str, extension: str) -> str:
    # The path uses only server-generated IDs; the user's filename is stored as metadata.
    return f"businesses/{business_id}/documents/{document_id}/original{extension}"
