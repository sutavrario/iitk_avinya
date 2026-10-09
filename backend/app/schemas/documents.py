from datetime import datetime
from typing import Literal

from app.schemas.common import ApiModel

DocumentKind = Literal["spreadsheet", "pdf", "image"]
# "uploaded" = original stored safely; extraction is not implemented yet.
DocumentStatus = Literal["uploaded", "processing", "completed", "failed"]


class UploadedDocumentOut(ApiModel):
    id: str
    file_name: str
    size_bytes: int
    kind: DocumentKind
    content_type: str
    status: DocumentStatus
    uploaded_at: datetime
    extracted_record_count: int | None = None
    error_message: str | None = None
