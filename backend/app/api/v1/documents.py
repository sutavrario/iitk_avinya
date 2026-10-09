import hashlib
from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, Form, Path, Response, UploadFile, status
from google.cloud.firestore_v1 import FieldFilter

from app.api.v1.deps import Db, StorageBucket
from app.core.config import get_settings
from app.core.errors import ConflictError
from app.core.logging import get_logger
from app.repositories import collections as col
from app.repositories import records as records_repo
from app.schemas.ingestion import (
    ConfirmRequest,
    ConfirmResponse,
    DocumentDetailOut,
    ExtractedRowOut,
    ProcessRequest,
    RowUpdate,
)
from app.services import ingestion_jobs, ingestion_review
from app.services.authorization import CanEdit, CanView
from app.services.documents import read_limited, storage_path, validate_upload
from app.services.ingestion_store import document_to_api, row_to_api

router = APIRouter(prefix="/businesses/{business_id}/documents", tags=["documents"])
logger = get_logger(__name__)

DocumentId = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{1,64}$")]
RowId = Annotated[str, Path(pattern=r"^row\d{5}$")]


@router.get("", response_model=list[DocumentDetailOut])
def list_documents(access: CanView, db: Db) -> list[DocumentDetailOut]:
    docs = records_repo.list_records(db, col.UPLOADED_DOCUMENTS, access, order_by="uploadedAt")
    return [document_to_api(d) for d in docs]


@router.post("", response_model=DocumentDetailOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    access: CanEdit,
    db: Db,
    bucket: StorageBucket,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File(description="Excel (.xlsx/.xls), CSV, PDF, JPG or PNG")],
    record_type: Annotated[
        Literal["sales_invoice", "purchase_invoice"], Form(alias="recordType")
    ] = "sales_invoice",
) -> DocumentDetailOut:
    """1) store the original privately, 2) create the document record, 3) queue background parsing."""
    upload = validate_upload(
        file.filename, read_limited(file.file, get_settings().max_upload_bytes)
    )
    digest = hashlib.sha256(upload.content).hexdigest()

    same_file = (
        db.collection(col.UPLOADED_DOCUMENTS)
        .where(filter=FieldFilter("businessId", "==", access.business_id))
        .where(filter=FieldFilter("sha256", "==", digest))
        .limit(1)
        .get()
    )
    ref = db.collection(col.UPLOADED_DOCUMENTS).document()
    path = storage_path(access.business_id, ref.id, upload.extension)
    blob = bucket.blob(path)
    blob.metadata = {
        "businessId": access.business_id,
        "uploadedBy": access.user.uid,
        "documentId": ref.id,
        "sha256": digest,
    }
    blob.upload_from_string(upload.content, content_type=upload.file_type.content_type)

    try:
        doc = records_repo.create_record(
            db,
            col.UPLOADED_DOCUMENTS,
            access,
            {
                "fileName": upload.original_name,
                "extension": upload.extension,
                "sizeBytes": len(upload.content),
                "kind": upload.file_type.kind,
                "contentType": upload.file_type.content_type,
                "sha256": digest,
                "storagePath": path,
                "recordType": record_type,
                "status": "queued",
                "duplicateOfDocumentId": same_file[0].id if same_file else None,
                "processing": {"run": 0, "attempts": 0},
                "confirmedCount": 0,
                "uploadedAt": datetime.now(UTC),
            },
            record_id=ref.id,
        )
    except Exception:
        blob.delete()  # don't leave an orphaned file
        raise

    run = ingestion_jobs.enqueue(db, access, ref.id, {})
    background.add_task(ingestion_jobs.run_job, access.business_id, ref.id, run)
    logger.info(
        "Stored document %s (%s, %d bytes); queued run %d",
        ref.id,
        upload.file_type.kind,
        len(upload.content),
        run,
    )
    return document_to_api(ingestion_review.load_document(db, access, doc["id"]))


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(document_id: DocumentId, access: CanView, db: Db) -> DocumentDetailOut:
    """Poll this for processing status."""
    return document_to_api(ingestion_review.load_document(db, access, document_id))


@router.post(
    "/{document_id}/process", response_model=DocumentDetailOut, status_code=status.HTTP_202_ACCEPTED
)
def process_document(
    document_id: DocumentId,
    body: ProcessRequest,
    access: CanEdit,
    db: Db,
    background: BackgroundTasks,
) -> DocumentDetailOut:
    """Retry, or re-run with a user-confirmed column mapping / sheet / record type."""
    doc = ingestion_review.load_document(db, access, document_id)
    if body.record_type and body.record_type != doc.get("recordType"):
        db.collection(col.UPLOADED_DOCUMENTS).document(document_id).update(
            {"recordType": body.record_type}
        )
    options = {
        "columnMapping": {k: v for k, v in body.column_mapping.items()}
        if body.column_mapping is not None
        else None,
        "sheetName": body.sheet_name,
        "forceOcr": body.force_ocr,
    }
    run = ingestion_jobs.enqueue(db, access, document_id, options)
    background.add_task(ingestion_jobs.run_job, access.business_id, document_id, run)
    return document_to_api(ingestion_review.load_document(db, access, document_id))


@router.get("/{document_id}/rows", response_model=list[ExtractedRowOut])
def list_rows(document_id: DocumentId, access: CanView, db: Db) -> list[ExtractedRowOut]:
    doc = ingestion_review.load_document(db, access, document_id)
    return [row_to_api(r, doc) for r in ingestion_review.list_rows(db, doc)]


@router.patch("/{document_id}/rows/{row_id}", response_model=ExtractedRowOut)
def update_row(
    document_id: DocumentId, row_id: RowId, body: RowUpdate, access: CanEdit, db: Db
) -> ExtractedRowOut:
    doc = ingestion_review.load_document(db, access, document_id)
    return row_to_api(ingestion_review.update_row(db, access, doc, row_id, body), doc)


@router.post("/{document_id}/confirm", response_model=ConfirmResponse)
def confirm_rows(
    document_id: DocumentId, body: ConfirmRequest, access: CanEdit, db: Db
) -> ConfirmResponse:
    """Save reviewed rows as invoices (sales) or expenses (purchases). Safe to call repeatedly."""
    doc = ingestion_review.load_document(db, access, document_id)
    return ingestion_review.confirm(db, access, doc, body.row_ids)


@router.get("/{document_id}/file")
def download_original(
    document_id: DocumentId, access: CanView, db: Db, bucket: StorageBucket
) -> Response:
    """The preserved original file, streamed through the API (bucket stays private)."""
    doc = ingestion_review.load_document(db, access, document_id)
    content = bucket.blob(doc["storagePath"]).download_as_bytes()
    filename = quote(doc["fileName"])
    return Response(
        content,
        media_type=doc["contentType"],
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: DocumentId, access: CanEdit, db: Db, bucket: StorageBucket
) -> None:
    doc = ingestion_review.load_document(db, access, document_id)
    if doc.get("confirmedCount", 0) > 0:
        raise ConflictError(
            "Records were saved from this document, so the original is kept as their source.",
            code="document_has_records",
        )
    if doc.get("status") in {"queued", "processing"}:
        raise ConflictError("Wait for processing to finish before deleting.", code="document_busy")
    doc_ref = db.collection(col.UPLOADED_DOCUMENTS).document(document_id)
    for snap in doc_ref.collection(col.EXTRACTED_RECORDS).stream():
        snap.reference.delete()
    db.collection(col.INGESTION_JOBS).document(document_id).delete()
    blob = bucket.blob(str(doc["storagePath"]))
    if blob.exists():
        blob.delete()
    doc_ref.delete()
