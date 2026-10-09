"""Authentication behaviour without Firebase: the verifier is faked or patched."""

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from firebase_admin import auth as fb_auth

from app.core import security
from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError, UnauthorizedError
from app.core.firebase import get_db
from app.core.security import AuthenticatedUser, FirebaseTokenVerifier, get_token_verifier
from app.main import app


class FakeVerifier:
    def verify(self, id_token: str) -> AuthenticatedUser:
        if id_token == "expired":
            raise UnauthorizedError("expired", code="token_expired")
        if id_token != "good":
            raise UnauthorizedError("bad", code="invalid_token")
        return AuthenticatedUser(
            uid="u1", email="u1@example.com", email_verified=True, name="U One"
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_token_verifier] = lambda: FakeVerifier()
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("headers", "code"),
    [
        ({}, "missing_token"),
        ({"Authorization": "Basic dXNlcjpwYXNz"}, "missing_token"),
        ({"Authorization": "Bearer"}, "missing_token"),
        ({"Authorization": "Bearer not-a-token"}, "invalid_token"),
        ({"Authorization": "Bearer expired"}, "token_expired"),
    ],
)
def test_protected_endpoints_reject_bad_credentials(
    client: TestClient, headers: dict[str, str], code: str
) -> None:
    for method, path in [
        ("GET", "/api/v1/me"),
        ("POST", "/api/v1/businesses"),
        ("GET", "/api/v1/businesses/abc123"),
        ("GET", "/api/v1/businesses/abc123/invoices"),
        ("GET", "/api/v1/businesses/abc123/documents"),
    ]:
        res = client.request(method, path, headers=headers, json={} if method == "POST" else None)
        assert res.status_code == 401, (method, path, res.text)
        body = res.json()["error"]
        assert body["code"] == code
        assert res.headers["WWW-Authenticate"] == "Bearer"
        assert body["request_id"]


def test_health_stays_public(client: TestClient) -> None:
    assert client.get("/api/v1/health").status_code == 200


def test_malformed_business_id_is_rejected(client: TestClient) -> None:
    res = client.get(
        "/api/v1/businesses/..%2Fusers/invoices", headers={"Authorization": "Bearer good"}
    )
    assert res.status_code in (404, 422)


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (fb_auth.ExpiredIdTokenError("x", cause=None), "token_expired"),
        (fb_auth.RevokedIdTokenError("x"), "token_revoked"),
        (fb_auth.UserDisabledError("x"), "user_disabled"),
        (fb_auth.InvalidIdTokenError("x"), "invalid_token"),
        (ValueError("x"), "invalid_token"),
    ],
)
def test_firebase_verifier_maps_errors(
    monkeypatch: pytest.MonkeyPatch, exc: Exception, code: str
) -> None:
    monkeypatch.setattr(security, "get_firebase_app", lambda: object())

    def raise_(*_: object, **__: object) -> None:
        raise exc

    monkeypatch.setattr(fb_auth, "verify_id_token", raise_)
    with pytest.raises(UnauthorizedError) as info:
        FirebaseTokenVerifier().verify("t")
    assert info.value.code == code


def test_firebase_verifier_checks_revocation(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(security, "get_firebase_app", lambda: object())

    def fake_verify(token: str, **kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"uid": "abc", "email": "a@b.c", "email_verified": True}

    monkeypatch.setattr(fb_auth, "verify_id_token", fake_verify)
    user = FirebaseTokenVerifier().verify("t")
    assert user.uid == "abc"
    assert captured["check_revoked"] is True


def test_unconfigured_firebase_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "")
    monkeypatch.setenv("FIREBASE_USE_EMULATORS", "false")
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.firebase._app", None)
    try:
        with pytest.raises(ServiceUnavailableError):
            FirebaseTokenVerifier().verify("t")
        res = TestClient(app).get("/api/v1/me", headers={"Authorization": "Bearer t"})
        assert res.status_code == 503
        assert res.json()["error"]["code"] == "firebase_not_configured"
    finally:
        get_settings.cache_clear()


def test_emulators_refused_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings

    with pytest.raises(ValueError, match="production"):
        Settings(app_env="production", firebase_use_emulators=True)
