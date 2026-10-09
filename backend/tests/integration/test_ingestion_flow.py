"""End-to-end ingestion against the Firebase emulators.

TestClient runs FastAPI background tasks before returning, so after an upload the job has
already finished — the same code path as production, just synchronous.
"""

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.firebase import get_db
from app.core.security import AuthenticatedUser
from app.services import ingestion_jobs
from app.services.authorization import BusinessAccess, Role
from tests.integration.conftest import AuthUser

SAMPLES = Path(__file__).resolve().parents[3] / "sample_data" / "ingestion"
Owner = tuple[AuthUser, str]
MakeUser = Callable[[str], AuthUser]


def upload(
    client: TestClient, owner: AuthUser, biz: str, name: str, record_type: str = "sales_invoice"
) -> dict[str, Any]:
    path = SAMPLES / name
    res = client.post(
        f"/api/v1/businesses/{biz}/documents",
        files={"file": (path.name, path.read_bytes())},
        data={"recordType": record_type},
        headers=owner.headers,
    )
    assert res.status_code == 201, res.text
    doc = client.get(
        f"/api/v1/businesses/{biz}/documents/{res.json()['id']}", headers=owner.headers
    ).json()
    return doc


def rows(client: TestClient, owner: AuthUser, biz: str, doc_id: str) -> list[dict[str, Any]]:
    res = client.get(f"/api/v1/businesses/{biz}/documents/{doc_id}/rows", headers=owner.headers)
    assert res.status_code == 200, res.text
    return res.json()


def confirm(
    client: TestClient, owner: AuthUser, biz: str, doc_id: str, row_ids: list[str] | None = None
) -> dict[str, Any]:
    res = client.post(
        f"/api/v1/businesses/{biz}/documents/{doc_id}/confirm",
        json={"rowIds": row_ids},
        headers=owner.headers,
    )
    assert res.status_code == 200, res.text
    return res.json()


def count(collection: str, biz: str) -> int:
    from google.cloud.firestore_v1 import FieldFilter

    return len(
        list(
            get_db()
            .collection(collection)
            .where(filter=FieldFilter("businessId", "==", biz))
            .stream()
        )
    )


# --- Happy path -----------------------------------------------------------------------------------


def test_spreadsheet_upload_review_confirm(client: TestClient, owner_with_business: Owner) -> None:
    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "sales_register.xlsx")
    assert doc["status"] == "needs_review", doc
    assert doc["processing"]["attempts"] == 1 and doc["processing"]["method"] == "spreadsheet"
    assert doc["extraction"]["rowCount"] == 4 and doc["extraction"]["mapping"]["tax"] == [
        "CGST",
        "SGST",
    ]

    drafts = rows(client, owner, biz, doc["id"])
    inv = drafts[0]["invoice"]
    assert inv["invoiceNumber"] == "INV-1001" and inv["documentId"] == doc["id"]
    assert inv["total"] == "48498.00" and inv["tax"] == "7398.00"
    assert inv["paymentStatus"] == "unknown" and inv["documentPaymentStatus"] == "unpaid"
    assert inv["source"]["rowNumber"] == 2 and inv["source"]["sheetName"] == "Sales"
    assert inv["source"]["storagePath"].endswith("/original.xlsx")

    result = confirm(client, owner, biz, doc["id"])
    assert result["created"] == 4 and result["documentStatus"] == "completed"

    invoices = client.get(f"/api/v1/businesses/{biz}/invoices", headers=owner.headers).json()
    assert len(invoices) == 4
    saved = next(i for i in invoices if i["invoiceNumber"] == "INV-1002")
    assert saved["status"] == "unknown"  # document said "Paid"; not assumed
    assert saved["source"] == "upload" and saved["documentId"] == doc["id"]
    assert saved["paymentReferences"] == ["UTR123456789"]

    record = get_db().collection("invoices").document(f"{doc['id']}_row00000").get().to_dict()
    assert record["sourceRef"]["rowNumber"] == 2 and record["documentPaymentStatus"] == "unpaid"
    assert record["businessId"] == biz and record["extraction"]["confidence"] > 0.9

    # Unconfirmed payment status is reported separately on the dashboard, not as money owed.
    dash = client.get(f"/api/v1/businesses/{biz}/dashboard", headers=owner.headers).json()
    assert dash["kpis"]["outstandingReceivables"] == 0
    assert dash["kpis"]["unconfirmedCount"] == 4


def test_confirm_twice_is_idempotent(client: TestClient, owner_with_business: Owner) -> None:
    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "legacy_bills.xls")
    assert confirm(client, owner, biz, doc["id"])["created"] == 2
    again = confirm(client, owner, biz, doc["id"], ["row00000", "row00001"])
    assert again["created"] == 0
    assert {r["outcome"] for r in again["results"]} == {"already_confirmed"}
    assert count("invoices", biz) == 2


def test_original_is_preserved_and_downloadable(
    client: TestClient, owner_with_business: Owner
) -> None:
    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "invoice_digital.pdf")
    res = client.get(f"/api/v1/businesses/{biz}/documents/{doc['id']}/file", headers=owner.headers)
    assert res.status_code == 200
    assert res.content == (SAMPLES / "invoice_digital.pdf").read_bytes()
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["x-content-type-options"] == "nosniff"
    assert "attachment" in res.headers["content-disposition"]

    confirm(client, owner, biz, doc["id"])
    # Once records exist, the source document can't be deleted or re-processed.
    assert (
        client.delete(
            f"/api/v1/businesses/{biz}/documents/{doc['id']}", headers=owner.headers
        ).status_code
        == 409
    )
    res = client.post(
        f"/api/v1/businesses/{biz}/documents/{doc['id']}/process", json={}, headers=owner.headers
    )
    assert res.status_code == 409 and res.json()["error"]["code"] == "already_confirmed"


def test_digital_pdf_extracts_fields(client: TestClient, owner_with_business: Owner) -> None:
    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "invoice_digital.pdf")
    assert doc["status"] == "needs_review" and doc["processing"]["method"] == "text_layer"
    inv = rows(client, owner, biz, doc["id"])[0]["invoice"]
    assert (inv["invoiceNumber"], inv["counterpartyName"], inv["total"]) == (
        "SGS/2026/0457",
        "Deshmukh Caterers",
        "14049.00",
    )
    assert inv["source"]["page"] == 1


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract not installed")
def test_photo_of_purchase_bill_becomes_expense(
    client: TestClient, owner_with_business: Owner
) -> None:
    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "bill_photo.png", record_type="purchase_invoice")
    assert doc["processing"]["method"] == "ocr" and doc["processing"]["ocrPages"] == 1
    row = rows(client, owner, biz, doc["id"])[0]
    assert row["invoice"]["recordType"] == "purchase_invoice"
    assert any(
        i["code"] == "low_confidence" for i in row["invoice"]["issues"]
    )  # repaired OCR invoice number
    assert confirm(client, owner, biz, doc["id"])["created"] == 1
    expenses = client.get(f"/api/v1/businesses/{biz}/expenses", headers=owner.headers).json()
    assert (
        expenses[0]["supplierName"] == "Bharat Wholesale Supplies" and expenses[0]["total"] == 23600
    )
    assert count("invoices", biz) == 0


# --- Validation, corrections, duplicates -------------------------------------------------------


def test_rows_with_errors_need_fixing_before_saving(
    client: TestClient, owner_with_business: Owner
) -> None:
    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "sales_with_problems.csv")
    drafts = rows(client, owner, biz, doc["id"])
    assert doc["extraction"]["errorRowCount"] >= 5

    missing_total = drafts[1]
    assert missing_total["invoice"]["total"] is None  # never 0
    assert (
        get_db()
        .collection("uploadedDocuments")
        .document(doc["id"])
        .collection("extractedRecords")
        .document("row00001")
        .get()
        .to_dict()["values"]["totalPaise"]
        is None
    )

    result = confirm(client, owner, biz, doc["id"])
    outcomes = {r["rowId"]: r["outcome"] for r in result["results"]}
    assert outcomes["row00001"] == "has_errors" and outcomes["row00002"] == "has_errors"
    assert outcomes["row00000"] == "created"
    assert outcomes["row00003"] == "duplicate"  # repeat of row00000 in the same file
    assert result["documentStatus"] == "needs_review"

    # Correct the missing total using the suggestion; the server re-validates.
    suggestion = next(i for i in missing_total["invoice"]["issues"] if i["field"] == "total")[
        "suggestedValue"
    ]
    base = f"/api/v1/businesses/{biz}/documents/{doc['id']}/rows"
    fixed = client.patch(
        f"{base}/row00001", json={"values": {"total": suggestion}}, headers=owner.headers
    ).json()
    assert fixed["invoice"]["total"] == "5900.00"
    assert not [i for i in fixed["invoice"]["issues"] if i["severity"] == "error"]
    assert (
        fixed["editedFields"] == ["total"] and fixed["raw"].get("total") is None
    )  # original "blank" preserved
    assert fixed["invoice"]["fieldConfidence"]["total"] == 1.0

    # A wrong correction is still caught.
    bad = client.patch(
        f"{base}/row00002", json={"values": {"total": "9000"}}, headers=owner.headers
    ).json()
    assert any(i["code"] == "total_mismatch" for i in bad["invoice"]["issues"])

    # Exclude rows we don't want; confirm the rest.
    for rid in ("row00002", "row00003", "row00004", "row00005", "row00006", "row00007"):
        client.patch(f"{base}/{rid}", json={"excluded": True}, headers=owner.headers)
    result = confirm(client, owner, biz, doc["id"])
    assert result["documentStatus"] == "completed"
    assert count("invoices", biz) == 2


def test_payment_status_set_by_user(client: TestClient, owner_with_business: Owner) -> None:
    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "invoice_digital.pdf")
    base = f"/api/v1/businesses/{biz}/documents/{doc['id']}/rows"
    row = client.patch(
        f"{base}/row00000",
        json={"paymentStatus": "unpaid", "paymentReferences": ["NEFT X1"]},
        headers=owner.headers,
    ).json()
    assert row["invoice"]["paymentStatus"] == "unpaid"
    assert not any(i["code"] == "payment_status_unverified" for i in row["invoice"]["issues"])
    confirm(client, owner, biz, doc["id"])
    inv = client.get(f"/api/v1/businesses/{biz}/invoices", headers=owner.headers).json()[0]
    # Due 18 Oct 2026; becomes "overdue" automatically after that because the user confirmed "unpaid".
    assert inv["status"] == "unpaid" and inv["dueDate"] == "2026-10-18"
    assert inv["paymentReferences"] == ["NEFT X1"]


def test_cross_document_duplicates(client: TestClient, owner_with_business: Owner) -> None:
    owner, biz = owner_with_business
    first = upload(client, owner, biz, "sales_register.xlsx")
    confirm(client, owner, biz, first["id"])

    second = upload(client, owner, biz, "duplicate_of_register.csv")
    drafts = rows(client, owner, biz, second["id"])
    dup = next(r for r in drafts if r["invoice"]["invoiceNumber"] == "INV-1001")
    issue = next(i for i in dup["invoice"]["issues"] if i["code"] == "possible_duplicate")
    assert issue["relatedRecordId"] == f"{first['id']}_row00000"

    result = confirm(client, owner, biz, second["id"])
    outcomes = {r["rowId"]: r["outcome"] for r in result["results"]}
    assert outcomes == {"row00000": "duplicate", "row00001": "created"}
    assert count("invoices", biz) == 5

    # The user says it's genuinely different → saved once, and only once.
    client.patch(
        f"/api/v1/businesses/{biz}/documents/{second['id']}/rows/row00000",
        json={"allowDuplicate": True},
        headers=owner.headers,
    )
    assert confirm(client, owner, biz, second["id"])["created"] == 1
    assert confirm(client, owner, biz, second["id"])["created"] == 0
    assert count("invoices", biz) == 6


def test_manual_invoice_duplicate_detection(client: TestClient, owner_with_business: Owner) -> None:
    owner, biz = owner_with_business
    body = {
        "invoiceNumber": "INV-77",
        "customerName": "Patel Agencies",
        "issueDate": "2026-09-01",
        "dueDate": "2026-09-30",
        "amount": "100",
    }
    url = f"/api/v1/businesses/{biz}/invoices"
    assert client.post(url, json=body, headers=owner.headers).status_code == 201
    res = client.post(url, json={**body, "invoiceNumber": "inv 77"}, headers=owner.headers)
    assert res.status_code == 409 and res.json()["error"]["code"] == "duplicate_invoice"
    assert (
        client.post(f"{url}?allowDuplicate=true", json=body, headers=owner.headers).status_code
        == 201
    )


def test_same_file_uploaded_twice_is_flagged(
    client: TestClient, owner_with_business: Owner
) -> None:
    owner, biz = owner_with_business
    first = upload(client, owner, biz, "purchase_bills.csv", "purchase_invoice")
    second = upload(client, owner, biz, "purchase_bills.csv", "purchase_invoice")
    assert second["duplicateOfDocumentId"] == first["id"]


# --- Column mapping ------------------------------------------------------------------------------


def test_column_mapping_step(client: TestClient, owner_with_business: Owner) -> None:
    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "unknown_columns.csv")
    assert doc["status"] == "needs_mapping"
    assert doc["extraction"]["columns"] == ["Col1", "Col2", "Col3", "Col4"]
    assert rows(client, owner, biz, doc["id"]) == []

    url = f"/api/v1/businesses/{biz}/documents/{doc['id']}/process"
    bad = client.post(url, json={"columnMapping": {"total": ["Nope"]}}, headers=owner.headers)
    assert bad.status_code == 202
    after = client.get(
        f"/api/v1/businesses/{biz}/documents/{doc['id']}", headers=owner.headers
    ).json()
    assert after["status"] == "failed" and after["processing"]["errorCode"] == "invalid_mapping"

    mapping = {
        "invoiceNumber": ["Col1"],
        "counterpartyName": ["Col2"],
        "invoiceDate": ["Col3"],
        "total": ["Col4"],
    }
    assert (
        client.post(url, json={"columnMapping": mapping}, headers=owner.headers).status_code == 202
    )
    after = client.get(
        f"/api/v1/businesses/{biz}/documents/{doc['id']}", headers=owner.headers
    ).json()
    assert after["status"] == "needs_review" and after["processing"]["run"] == 3
    assert len(rows(client, owner, biz, doc["id"])) == 2
    smuggled = client.post(
        url, json={"columnMapping": mapping, "businessId": "x"}, headers=owner.headers
    )
    assert smuggled.status_code == 422


# --- Failures, retries, idempotent jobs -----------------------------------------------------------


def test_malformed_file_fails_and_can_be_retried(
    client: TestClient, owner_with_business: Owner
) -> None:
    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "malformed/corrupt.xlsx")
    assert doc["status"] == "failed"
    assert doc["processing"]["errorCode"] == "malformed_file" and doc["processing"]["errorMessage"]
    res = client.post(
        f"/api/v1/businesses/{biz}/documents/{doc['id']}/process", json={}, headers=owner.headers
    )
    assert res.status_code == 202
    again = client.get(
        f"/api/v1/businesses/{biz}/documents/{doc['id']}", headers=owner.headers
    ).json()
    assert again["status"] == "failed" and again["processing"]["attempts"] == 2
    # A failed document can be deleted (nothing was saved from it).
    assert (
        client.delete(
            f"/api/v1/businesses/{biz}/documents/{doc['id']}", headers=owner.headers
        ).status_code
        == 204
    )


def _access(owner: AuthUser, biz: str) -> BusinessAccess:
    return BusinessAccess(
        business_id=biz, user=AuthenticatedUser(owner.uid, owner.email, True, None), role=Role.OWNER
    )


def test_duplicate_job_delivery_does_not_duplicate_rows(
    client: TestClient, owner_with_business: Owner
) -> None:
    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "tally_sales_export.xlsx")
    db = get_db()
    run = ingestion_jobs.enqueue(db, _access(owner, biz), doc["id"], {})
    ingestion_jobs.run_job(biz, doc["id"], run)
    ingestion_jobs.run_job(biz, doc["id"], run)  # duplicate delivery → no-op
    ingestion_jobs.run_job(biz, doc["id"], run - 1)  # stale run → no-op
    after = client.get(
        f"/api/v1/businesses/{biz}/documents/{doc['id']}", headers=owner.headers
    ).json()
    assert after["processing"]["run"] == run and after["processing"]["attempts"] == 2
    all_rows = list(
        db.collection("uploadedDocuments")
        .document(doc["id"])
        .collection("extractedRecords")
        .stream()
    )
    assert len(all_rows) == 3  # old run's rows replaced, not added to
    assert {r.to_dict()["run"] for r in all_rows} == {run}


def test_cannot_enqueue_while_running_until_lease_expires(
    client: TestClient, owner_with_business: Owner
) -> None:
    from datetime import UTC, datetime, timedelta

    from app.core.errors import ConflictError

    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "legacy_bills.xls")
    db = get_db()
    access = _access(owner, biz)
    run = ingestion_jobs.enqueue(db, access, doc["id"], {})
    with pytest.raises(ConflictError):
        ingestion_jobs.enqueue(db, access, doc["id"], {})
    # Simulate a crashed worker: lease expired → a retry is allowed and can claim it.
    db.collection("ingestionJobs").document(doc["id"]).update(
        {"status": "running", "leaseExpiresAt": datetime.now(UTC) - timedelta(seconds=1)}
    )
    run2 = ingestion_jobs.enqueue(db, access, doc["id"], {})
    assert run2 == run + 1
    ingestion_jobs.run_job(biz, doc["id"], run2)
    assert (
        client.get(f"/api/v1/businesses/{biz}/documents/{doc['id']}", headers=owner.headers).json()[
            "status"
        ]
        == "needs_review"
    )


# --- Authorization -------------------------------------------------------------------------------


def test_other_business_cannot_touch_documents(
    client: TestClient, owner_with_business: Owner, make_user: MakeUser
) -> None:
    from tests.integration.conftest import PROFILE

    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "sales_register.xlsx")
    bob = make_user("bob")
    bob_biz = client.post("/api/v1/businesses", json=PROFILE, headers=bob.headers).json()["id"]
    d = doc["id"]
    for method, path, body in [
        ("GET", f"/{biz}/documents/{d}", None),
        ("GET", f"/{biz}/documents/{d}/rows", None),
        ("GET", f"/{biz}/documents/{d}/file", None),
        ("PATCH", f"/{biz}/documents/{d}/rows/row00000", {"excluded": True}),
        ("POST", f"/{biz}/documents/{d}/confirm", {}),
        ("POST", f"/{biz}/documents/{d}/process", {}),
        # Bob's own business in the URL with Alice's document ID:
        ("GET", f"/{bob_biz}/documents/{d}", None),
        ("GET", f"/{bob_biz}/documents/{d}/rows", None),
        ("POST", f"/{bob_biz}/documents/{d}/confirm", {}),
        ("GET", f"/{bob_biz}/documents/{d}/file", None),
    ]:
        res = client.request(method, f"/api/v1/businesses{path}", json=body, headers=bob.headers)
        assert res.status_code == 404, (method, path, res.text)
    assert count("invoices", biz) == 0 and count("invoices", bob_biz) == 0


def test_viewer_cannot_edit_or_confirm(
    client: TestClient, owner_with_business: Owner, make_user: MakeUser
) -> None:
    owner, biz = owner_with_business
    doc = upload(client, owner, biz, "legacy_bills.xls")
    viewer = make_user("viewer")
    get_db().collection("businessMembers").document(f"{biz}_{viewer.uid}").set(
        {"businessId": biz, "uid": viewer.uid, "role": "viewer"}
    )
    base = f"/api/v1/businesses/{biz}/documents/{doc['id']}"
    assert client.get(f"{base}/rows", headers=viewer.headers).status_code == 200
    assert (
        client.patch(
            f"{base}/rows/row00000", json={"excluded": True}, headers=viewer.headers
        ).status_code
        == 403
    )
    assert client.post(f"{base}/confirm", json={}, headers=viewer.headers).status_code == 403
    assert client.post(f"{base}/process", json={}, headers=viewer.headers).status_code == 403
