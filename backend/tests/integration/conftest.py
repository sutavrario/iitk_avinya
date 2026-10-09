"""Integration tests against the Firebase emulators (Auth, Firestore, Storage).

Run with:  ./scripts/test_integration.sh   (wraps `firebase emulators:exec`)
Skipped automatically when FIREBASE_USE_EMULATORS is not set.
"""

import os
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import EMULATOR_PROJECT_ID, get_settings

if os.environ.get("FIREBASE_USE_EMULATORS", "").lower() != "true":
    pytest.skip("Firebase emulators not enabled", allow_module_level=True)

AUTH = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
FIRESTORE = os.environ.get("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")


@dataclass
class AuthUser:
    uid: str
    email: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


def _sign_up(email: str, password: str = "test-password-123") -> AuthUser:
    res = httpx.post(
        f"http://{AUTH}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key",
        json={"email": email, "password": password, "returnSecureToken": True},
    )
    res.raise_for_status()
    body = res.json()
    return AuthUser(uid=body["localId"], email=email, token=body["idToken"])


@pytest.fixture(autouse=True)
def _clean_emulators() -> Iterator[None]:
    get_settings.cache_clear()
    assert get_settings().effective_project_id == EMULATOR_PROJECT_ID
    yield
    httpx.delete(
        f"http://{FIRESTORE}/emulator/v1/projects/{EMULATOR_PROJECT_ID}/databases/(default)/documents"
    )
    httpx.delete(f"http://{AUTH}/emulator/v1/projects/{EMULATOR_PROJECT_ID}/accounts")


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def make_user() -> Callable[[str], AuthUser]:
    def factory(name: str) -> AuthUser:
        return _sign_up(f"{name}-{uuid.uuid4().hex[:8]}@example.com")

    return factory


PROFILE = {
    "businessName": "Sharma General Store",
    "industry": "retail",
    "businessType": "proprietorship",
    "location": {"city": "Pune", "state": "Maharashtra", "pincode": "411001"},
    "currency": "INR",
    "financialYearStart": "april",
    "paymentTermsDays": 30,
    "goals": ["collect_payments_faster", "gst_compliance"],
    "preferredLanguage": "hi",
    "gstin": "27ABCDE1234F1Z5",
}


@pytest.fixture
def owner_with_business(
    client: TestClient, make_user: Callable[[str], AuthUser]
) -> tuple[AuthUser, str]:
    owner = make_user("alice")
    res = client.post("/api/v1/businesses", json=PROFILE, headers=owner.headers)
    assert res.status_code == 201, res.text
    return owner, res.json()["id"]
