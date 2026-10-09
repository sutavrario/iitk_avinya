"""Serialization between pipeline drafts, Firestore documents and API models."""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore_v1 import FieldFilter

from app.core.config import Settings
from app.ingestion.drafts import Draft, Issue, build_draft
from app.ingestion.ocr import OcrProvider, build_ocr_provider
from app.ingestion.text_extractor import ExtractionProvider, build_extraction_provider
from app.repositories import collections as col
from app.repositories.money import from_paise, to_paise
from app.schemas.ingestion import (
    DocumentDetailOut,
    ExtractedRowOut,
    ExtractionInfo,
    NormalizedInvoice,
    ProcessingInfo,
    SourceReference,
    ValidationIssue,
)

TARGET_COLLECTION = {"sales_invoice": col.INVOICES, "purchase_invoice": col.EXPENSES}
EDITABLE_FIELDS = (
    "invoiceNumber",
    "counterpartyName",
    "invoiceDate",
    "dueDate",
    "currency",
    "subtotal",
    "tax",
    "total",
)


def providers(settings: Settings) -> tuple[OcrProvider, ExtractionProvider]:
    ocr = build_ocr_provider(
        settings.ocr_provider,
        settings.ocr_languages,
        settings.tesseract_cmd,
        settings.ocr_timeout_seconds,
    )
    return ocr, build_extraction_provider(settings.extraction_provider)


# --- Drafts → Firestore -----------------------------------------------------------------------


def _paise(amount: Decimal | None) -> int | None:
    return None if amount is None else to_paise(amount)


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def stored_values(draft: Draft) -> dict[str, Any]:
    v = draft.values
    return {
        "invoiceNumber": v.invoice_number,
        "counterpartyName": v.counterparty_name,
        "invoiceDate": _iso(v.invoice_date),
        "dueDate": _iso(v.due_date),
        "currency": v.currency,
        "subtotalPaise": _paise(v.subtotal),
        "taxPaise": _paise(v.tax),
        "totalPaise": _paise(v.total),
        "paymentStatus": v.payment_status,
        "documentPaymentStatus": v.document_payment_status,
        "paymentReferences": v.payment_references,
    }


def draft_fields(draft: Draft) -> dict[str, Any]:
    """The parts of a stored row that are recomputed whenever the row is (re)validated."""
    return {
        "values": stored_values(draft),
        "fieldConfidence": draft.field_confidence,
        "confidence": draft.confidence,
        "issues": [i.to_dict() for i in draft.issues],
        "dedupeKey": draft.dedupe_key,
        "hasErrors": draft.has_errors,
    }


def input_strings(values: dict[str, Any]) -> dict[str, str | None]:
    """Raw extracted values as strings (Firestore-safe, and re-parseable by build_draft)."""
    out: dict[str, str | None] = {}
    for k, v in values.items():
        if v is None:
            out[k] = None
        elif hasattr(v, "isoformat"):
            out[k] = str(v.isoformat())[:10]
        elif isinstance(v, float) and v.is_integer():
            out[k] = str(int(v))
        else:
            out[k] = str(v)
    return out


def rebuild(row: dict[str, Any], record_type: str, today: date) -> Draft:
    """Re-run normalization + validation on a stored row's current inputs."""
    return build_draft(
        row.get("input") or {},
        record_type=record_type,
        today=today,
        field_confidence=row.get("inputConfidence") or {},
        payment_references=row.get("paymentReferences") or [],
        user_payment_status=row.get("userPaymentStatus"),
        date_orders=row.get("dateOrders") or {},
    )


# --- Duplicates -------------------------------------------------------------------------------


def find_existing(
    db: FirestoreClient, business_id: str, record_type: str, keys: Iterable[str]
) -> dict[str, str]:
    """dedupeKey → existing confirmed record ID, scoped to one business."""
    collection = TARGET_COLLECTION[record_type]
    unique = sorted({k for k in keys if k})
    found: dict[str, str] = {}
    for i in range(0, len(unique), 30):  # Firestore `in` limit
        query = (
            db.collection(collection)
            .where(filter=FieldFilter("businessId", "==", business_id))
            .where(filter=FieldFilter("dedupeKey", "in", unique[i : i + 30]))
        )
        for snap in query.stream():
            found.setdefault(snap.get("dedupeKey"), snap.id)
    return found


def add_duplicate_issue(
    issues: list[dict[str, Any]], record_id: str, own_record_id: str | None
) -> list[dict[str, Any]]:
    issues = [i for i in issues if i.get("code") != "possible_duplicate"]
    if record_id and record_id != own_record_id:
        issues.append(
            Issue(
                "possible_duplicate",
                "warning",
                "An invoice with this number and party is already saved. It won't be saved again unless you mark it as not a duplicate.",
                "invoiceNumber",
                related_record_id=record_id,
            ).to_dict()
        )
    return issues


# --- Firestore → API --------------------------------------------------------------------------


def _amount(paise: int | None) -> Decimal | None:
    return None if paise is None else (Decimal(paise) / 100).quantize(Decimal("0.01"))


def source_ref(doc: dict[str, Any], source: dict[str, Any]) -> SourceReference:
    return SourceReference(
        document_id=doc["id"],
        file_name=doc["fileName"],
        storage_path=doc["storagePath"],
        method=source.get("method", "spreadsheet"),
        sheet_name=source.get("sheetName"),
        row_number=source.get("rowNumber"),
        page=source.get("page"),
        snippet=source.get("snippet"),
    )


def row_to_api(row: dict[str, Any], doc: dict[str, Any]) -> ExtractedRowOut:
    v = row.get("values") or {}
    invoice = NormalizedInvoice(
        invoice_number=v.get("invoiceNumber"),
        document_id=doc["id"],
        record_type=doc.get("recordType", "sales_invoice"),
        counterparty_name=v.get("counterpartyName"),
        invoice_date=v.get("invoiceDate"),
        due_date=v.get("dueDate"),
        currency=v.get("currency"),
        subtotal=_amount(v.get("subtotalPaise")),
        tax=_amount(v.get("taxPaise")),
        total=_amount(v.get("totalPaise")),
        payment_status=v.get("paymentStatus", "unknown"),
        document_payment_status=v.get("documentPaymentStatus"),
        payment_references=v.get("paymentReferences") or [],
        confidence=row.get("confidence", 0.0),
        field_confidence=row.get("fieldConfidence") or {},
        issues=[ValidationIssue.model_validate(i) for i in row.get("issues") or []],
        source=source_ref(doc, row.get("source") or {}),
    )
    return ExtractedRowOut(
        id=row["id"],
        index=row.get("index", 0),
        invoice=invoice,
        raw=row.get("raw") or {},
        edited_fields=row.get("editedFields") or [],
        excluded=bool(row.get("excluded")),
        allow_duplicate=bool(row.get("allowDuplicate")),
        confirmed_record_id=row.get("confirmedRecordId"),
    )


def document_to_api(doc: dict[str, Any]) -> DocumentDetailOut:
    processing = doc.get("processing") or {}
    extraction = doc.get("extraction")
    return DocumentDetailOut(
        id=doc["id"],
        file_name=doc["fileName"],
        size_bytes=doc["sizeBytes"],
        kind=doc["kind"],
        content_type=doc["contentType"],
        status=doc.get("status", "uploaded"),
        record_type=doc.get("recordType", "sales_invoice"),
        uploaded_at=doc["uploadedAt"],
        uploaded_by=doc.get("createdBy"),
        duplicate_of_document_id=doc.get("duplicateOfDocumentId"),
        processing=ProcessingInfo.model_validate(processing),
        extraction=ExtractionInfo.model_validate(extraction) if extraction else None,
        confirmed_count=doc.get("confirmedCount", 0),
    )


def record_from_row(row: dict[str, Any], doc: dict[str, Any], uid: str, now: Any) -> dict[str, Any]:
    """The confirmed Firestore record (invoices or expenses) for a reviewed row."""
    v = row["values"]
    record_type = doc.get("recordType", "sales_invoice")
    warnings = [i for i in row.get("issues") or [] if i.get("severity") != "error"]
    common = {
        "recordType": record_type,
        "invoiceNumber": v["invoiceNumber"],
        "counterpartyName": v["counterpartyName"],
        "currency": v["currency"],
        "subtotalPaise": v.get("subtotalPaise"),
        "taxPaise": v.get("taxPaise"),
        "totalPaise": v["totalPaise"],
        "paymentStatus": v.get("paymentStatus", "unknown"),
        "documentPaymentStatus": v.get("documentPaymentStatus"),
        "paymentReferences": v.get("paymentReferences") or [],
        "documentId": doc["id"],
        "sourceRef": {
            **(row.get("source") or {}),
            "documentId": doc["id"],
            "storagePath": doc["storagePath"],
            "fileName": doc["fileName"],
            "rowId": row["id"],
        },
        "extraction": {
            "confidence": row.get("confidence"),
            "fieldConfidence": row.get("fieldConfidence") or {},
            "issues": warnings,
        },
        "dedupeKey": row.get("dedupeKey"),
        "source": "upload",
        "businessId": doc["businessId"],
        "createdBy": uid,
        "confirmedBy": uid,
        "createdAt": now,
        "updatedAt": now,
    }
    if record_type == "sales_invoice":
        # Fields shared with manually entered invoices (records list, dashboard).
        return {
            **common,
            "customerName": v["counterpartyName"],
            "issueDate": v["invoiceDate"],
            "dueDate": v.get("dueDate"),  # stays null when unknown; never guessed
            "amountPaise": v["totalPaise"],
            "gstAmountPaise": v.get("taxPaise"),
            "status": v.get("paymentStatus", "unknown"),
        }
    return {
        **common,
        "supplierName": v["counterpartyName"],
        "date": v["invoiceDate"],
        "dueDate": v.get("dueDate"),
    }


def money(paise: int | None) -> float | None:
    return None if paise is None else from_paise(paise)
