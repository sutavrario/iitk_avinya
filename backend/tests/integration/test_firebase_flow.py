import time
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from firebase_admin import auth as fb_auth

from app.core.firebase import get_bucket, get_db, get_firebase_app
from tests.integration.conftest import PROFILE, AuthUser

Owner = tuple[AuthUser, str]
MakeUser = Callable[[str], AuthUser]

INVOICE = {
    "invoiceNumber": "INV-1",
    "customerName": "Patel Agencies",
    "issueDate": "2026-09-01",
    "dueDate": "2026-09-15",
    "amount": "48500.50",
    "gstAmount": "7398.38",
}


# --- Authentication ---------------------------------------------------------------------


def test_real_emulator_token_is_accepted_and_profile_created(
    client: TestClient, make_user: MakeUser
) -> None:
    user = make_user("new")
    res = client.get("/api/v1/me", headers=user.headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user"]["uid"] == user.uid
    assert body["user"]["email"] == user.email
    assert body["user"]["defaultBusinessId"] is None
    assert body["memberships"] == []
    stored = get_db().collection("users").document(user.uid).get()
    assert stored.exists and stored.to_dict()["email"] == user.email


def test_garbage_token_rejected(client: TestClient) -> None:
    res = client.get("/api/v1/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_token"


def test_revoked_session_rejected(client: TestClient, make_user: MakeUser) -> None:
    user = make_user("revoked")
    assert client.get("/api/v1/me", headers=user.headers).status_code == 200
    time.sleep(1.1)  # revocation is second-granular
    fb_auth.revoke_refresh_tokens(user.uid, app=get_firebase_app())
    res = client.get("/api/v1/me", headers=user.headers)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "token_revoked"


def test_disabled_user_rejected(client: TestClient, make_user: MakeUser) -> None:
    user = make_user("disabled")
    fb_auth.update_user(user.uid, disabled=True, app=get_firebase_app())
    res = client.get("/api/v1/me", headers=user.headers)
    assert res.status_code == 401
    assert res.json()["error"]["code"] in {"user_disabled", "token_revoked"}


# --- Profile persistence -----------------------------------------------------------------


def test_onboarding_persists_business_and_membership(
    client: TestClient, owner_with_business: Owner
) -> None:
    owner, biz_id = owner_with_business

    me = client.get("/api/v1/me", headers=owner.headers).json()
    assert me["user"]["defaultBusinessId"] == biz_id
    # Onboarding language seeds preferences; other preference fields keep their defaults.
    assert me["user"]["preferences"]["copilotLanguage"] == "hi"
    assert me["user"]["preferences"]["numberFormat"] == "indian"
    assert me["memberships"] == [
        {"businessId": biz_id, "businessName": PROFILE["businessName"], "role": "owner"}
    ]

    got = client.get(f"/api/v1/businesses/{biz_id}", headers=owner.headers).json()
    for key in (
        "businessName",
        "industry",
        "location",
        "goals",
        "preferredLanguage",
        "gstin",
        "paymentTermsDays",
    ):
        assert got[key] == PROFILE[key]
    assert got["role"] == "owner"

    db = get_db()
    stored = db.collection("businesses").document(biz_id).get().to_dict()
    assert stored["ownerUid"] == owner.uid
    member = db.collection("businessMembers").document(f"{biz_id}_{owner.uid}").get().to_dict()
    assert member == {**member, "businessId": biz_id, "uid": owner.uid, "role": "owner"}


def test_update_business_persists(client: TestClient, owner_with_business: Owner) -> None:
    owner, biz_id = owner_with_business
    updated = {**PROFILE, "businessName": "Sharma & Sons", "paymentTermsDays": None, "gstin": None}
    res = client.put(f"/api/v1/businesses/{biz_id}", json=updated, headers=owner.headers)
    assert res.status_code == 200, res.text
    again = client.get(f"/api/v1/businesses/{biz_id}", headers=owner.headers).json()
    assert again["businessName"] == "Sharma & Sons"
    assert again["paymentTermsDays"] is None
    assert again["gstin"] is None


def test_second_business_is_a_conflict(client: TestClient, owner_with_business: Owner) -> None:
    owner, _ = owner_with_business
    res = client.post("/api/v1/businesses", json=PROFILE, headers=owner.headers)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "business_exists"


def test_preferences_round_trip(client: TestClient, make_user: MakeUser) -> None:
    user = make_user("prefs")
    prefs = {
        "interfaceLanguage": "en",
        "copilotLanguage": "ta",
        "alwaysTranslateReplies": True,
        "showOriginalAlongsideTranslation": False,
        "numberFormat": "indian",
    }
    assert client.put("/api/v1/me/preferences", json=prefs, headers=user.headers).status_code == 200
    assert client.get("/api/v1/me/preferences", headers=user.headers).json() == prefs
    bad = client.put(
        "/api/v1/me/preferences", json={**prefs, "copilotLanguage": "xx"}, headers=user.headers
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "validation_error"


# --- Authorization -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "", None),
        ("PUT", "", PROFILE),
        ("GET", "/dashboard", None),
        ("GET", "/invoices", None),
        ("POST", "/invoices", INVOICE),
        ("GET", "/payments", None),
        ("GET", "/documents", None),
        ("DELETE", "/documents/someDocId", None),
    ],
)
def test_other_users_cannot_access_a_business(
    client: TestClient,
    owner_with_business: Owner,
    make_user: MakeUser,
    method: str,
    path: str,
    body: object,
) -> None:
    _, biz_id = owner_with_business
    intruder = make_user("mallory")
    res = client.request(
        method, f"/api/v1/businesses/{biz_id}{path}", json=body, headers=intruder.headers
    )
    assert res.status_code == 404, res.text
    assert res.json()["error"]["code"] == "business_not_found"
    # Identical response for a business that doesn't exist (no enumeration).
    res2 = client.request(
        method, f"/api/v1/businesses/doesNotExist{path}", json=body, headers=intruder.headers
    )
    assert res2.status_code == 404
    assert res2.json()["error"]["message"] == res.json()["error"]["message"]


def test_client_supplied_business_id_is_never_trusted(
    client: TestClient, owner_with_business: Owner, make_user: MakeUser
) -> None:
    owner, biz_a = owner_with_business
    bob = make_user("bob")
    biz_b = client.post("/api/v1/businesses", json=PROFILE, headers=bob.headers).json()["id"]

    # Bob tries to write into Alice's business by putting her ID in the body.
    res = client.post(
        f"/api/v1/businesses/{biz_b}/invoices",
        json={**INVOICE, "businessId": biz_a},
        headers=bob.headers,
    )
    assert res.status_code == 422

    # A normal create is always stamped with the business from the authorized URL.
    res = client.post(f"/api/v1/businesses/{biz_b}/invoices", json=INVOICE, headers=bob.headers)
    assert res.status_code == 201
    stored = get_db().collection("invoices").document(res.json()["id"]).get().to_dict()
    assert stored["businessId"] == biz_b
    assert stored["createdBy"] == bob.uid

    # Neither business sees the other's records.
    assert client.get(f"/api/v1/businesses/{biz_a}/invoices", headers=owner.headers).json() == []
    assert len(client.get(f"/api/v1/businesses/{biz_b}/invoices", headers=bob.headers).json()) == 1


def test_viewer_role_is_read_only(
    client: TestClient, owner_with_business: Owner, make_user: MakeUser
) -> None:
    _, biz_id = owner_with_business
    viewer = make_user("viewer")
    get_db().collection("businessMembers").document(f"{biz_id}_{viewer.uid}").set(
        {"businessId": biz_id, "uid": viewer.uid, "role": "viewer"}
    )
    assert client.get(f"/api/v1/businesses/{biz_id}", headers=viewer.headers).status_code == 200
    assert (
        client.get(f"/api/v1/businesses/{biz_id}/invoices", headers=viewer.headers).status_code
        == 200
    )
    for method, path, body in [
        ("POST", "/invoices", INVOICE),
        ("PUT", "", PROFILE),
    ]:
        res = client.request(
            method, f"/api/v1/businesses/{biz_id}{path}", json=body, headers=viewer.headers
        )
        assert res.status_code == 403, res.text
        assert res.json()["error"]["code"] == "insufficient_role"


def test_member_cannot_edit_business_profile(
    client: TestClient, owner_with_business: Owner, make_user: MakeUser
) -> None:
    _, biz_id = owner_with_business
    member = make_user("member")
    get_db().collection("businessMembers").document(f"{biz_id}_{member.uid}").set(
        {"businessId": biz_id, "uid": member.uid, "role": "member"}
    )
    assert (
        client.post(
            f"/api/v1/businesses/{biz_id}/invoices", json=INVOICE, headers=member.headers
        ).status_code
        == 201
    )
    assert (
        client.put(f"/api/v1/businesses/{biz_id}", json=PROFILE, headers=member.headers).status_code
        == 403
    )


def test_tampered_membership_document_is_rejected(
    client: TestClient, owner_with_business: Owner, make_user: MakeUser
) -> None:
    _, biz_id = owner_with_business
    user = make_user("tamper")
    # Membership doc ID matches, but its content points elsewhere -> not trusted.
    get_db().collection("businessMembers").document(f"{biz_id}_{user.uid}").set(
        {"businessId": "other", "uid": user.uid, "role": "owner"}
    )
    assert client.get(f"/api/v1/businesses/{biz_id}", headers=user.headers).status_code == 404


# --- Records & dashboard --------------------------------------------------------------------


def test_records_and_dashboard(client: TestClient, owner_with_business: Owner) -> None:
    owner, biz_id = owner_with_business
    base = f"/api/v1/businesses/{biz_id}"
    empty = client.get(f"{base}/dashboard", headers=owner.headers).json()
    assert empty["hasData"] is False and empty["isMock"] is False

    inv = client.post(f"{base}/invoices", json=INVOICE, headers=owner.headers).json()
    assert inv["amount"] == 48500.5
    assert inv["status"] == "overdue"  # derived from dueDate in the past
    pay = client.post(
        f"{base}/payments",
        json={
            "date": "2026-09-20",
            "partyName": "Patel Agencies",
            "direction": "received",
            "amount": "10000",
            "method": "upi",
        },
        headers=owner.headers,
    )
    assert pay.status_code == 201, pay.text

    dash = client.get(f"{base}/dashboard", headers=owner.headers).json()
    assert dash["hasData"] is True
    assert dash["kpis"]["totalSales"] == 48500.5
    assert dash["kpis"]["cashCollected"] == 10000
    assert dash["topCustomers"][0]["customerName"] == "Patel Agencies"


def test_validation_errors_use_envelope(client: TestClient, owner_with_business: Owner) -> None:
    owner, biz_id = owner_with_business
    res = client.post(
        f"/api/v1/businesses/{biz_id}/invoices",
        json={**INVOICE, "dueDate": "2026-08-01", "amount": "abc"},
        headers=owner.headers,
    )
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "validation_error"
    assert any("amount" in d["loc"] for d in err["details"])


# --- Documents -------------------------------------------------------------------------------


def test_document_upload_list_delete(client: TestClient, owner_with_business: Owner) -> None:
    owner, biz_id = owner_with_business
    base = f"/api/v1/businesses/{biz_id}/documents"
    res = client.post(
        base,
        files={
            "file": (
                "../../sales sept.csv",
                b"Invoice No,Customer,Date,Total\nA1,X,2026-09-01,100\n",
                "text/plain",
            )
        },
        headers=owner.headers,
    )
    assert res.status_code == 201, res.text
    doc = res.json()
    assert doc["fileName"] == "sales sept.csv"
    assert doc["contentType"] == "text/csv"  # decided by the server, not the client header

    stored = get_db().collection("uploadedDocuments").document(doc["id"]).get().to_dict()
    assert stored["businessId"] == biz_id
    assert stored["storagePath"] == f"businesses/{biz_id}/documents/{doc['id']}/original.csv"
    blob = get_bucket().blob(stored["storagePath"])
    assert blob.exists()

    assert [d["id"] for d in client.get(base, headers=owner.headers).json()] == [doc["id"]]
    assert client.delete(f"{base}/{doc['id']}", headers=owner.headers).status_code == 204
    assert not blob.exists()
    assert client.get(base, headers=owner.headers).json() == []
    assert client.delete(f"{base}/{doc['id']}", headers=owner.headers).status_code == 404


@pytest.mark.parametrize(
    ("name", "content", "status", "code"),
    [
        ("evil.exe", b"MZ\x90", 415, "unsupported_file_type"),
        ("fake.pdf", b"<script>", 415, "file_content_mismatch"),
        ("empty.csv", b"", 400, "empty_file"),
    ],
)
def test_bad_uploads_rejected(
    client: TestClient,
    owner_with_business: Owner,
    name: str,
    content: bytes,
    status: int,
    code: str,
) -> None:
    owner, biz_id = owner_with_business
    res = client.post(
        f"/api/v1/businesses/{biz_id}/documents",
        files={"file": (name, content)},
        headers=owner.headers,
    )
    assert res.status_code == status, res.text
    assert res.json()["error"]["code"] == code


def test_oversized_upload_rejected(
    client: TestClient, owner_with_business: Owner, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, biz_id = owner_with_business
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "100")
    from app.core.config import get_settings

    get_settings.cache_clear()
    res = client.post(
        f"/api/v1/businesses/{biz_id}/documents",
        files={"file": ("big.csv", b"a,b\n" * 100)},
        headers=owner.headers,
    )
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "file_too_large"


def test_cannot_delete_another_business_document(
    client: TestClient, owner_with_business: Owner, make_user: MakeUser
) -> None:
    owner, biz_a = owner_with_business
    doc_id = client.post(
        f"/api/v1/businesses/{biz_a}/documents",
        files={"file": ("a.csv", b"x,y\n")},
        headers=owner.headers,
    ).json()["id"]
    bob = make_user("bob")
    biz_b = client.post("/api/v1/businesses", json=PROFILE, headers=bob.headers).json()["id"]
    # Bob uses HIS business in the URL but Alice's document ID.
    res = client.delete(f"/api/v1/businesses/{biz_b}/documents/{doc_id}", headers=bob.headers)
    assert res.status_code == 404
    assert get_db().collection("uploadedDocuments").document(doc_id).get().exists
