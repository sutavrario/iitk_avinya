"""Authentication: verify Firebase ID tokens sent as `Authorization: Bearer <token>`."""

from dataclasses import dataclass
from typing import Annotated, Protocol

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as fb_auth

from app.core.errors import ServiceUnavailableError, UnauthorizedError
from app.core.firebase import get_firebase_app
from app.core.logging import get_logger

logger = get_logger(__name__)

_bearer = HTTPBearer(auto_error=False, description="Firebase ID token")


@dataclass(frozen=True)
class AuthenticatedUser:
    uid: str
    email: str | None
    email_verified: bool
    name: str | None


class TokenVerifier(Protocol):
    def verify(self, id_token: str) -> AuthenticatedUser: ...


class FirebaseTokenVerifier:
    """Verifies signature, expiry, audience (project) and revocation of Firebase ID tokens."""

    def verify(self, id_token: str) -> AuthenticatedUser:
        app = get_firebase_app()
        try:
            claims = fb_auth.verify_id_token(
                id_token, app=app, check_revoked=True, clock_skew_seconds=5
            )
        except fb_auth.ExpiredIdTokenError as exc:
            raise UnauthorizedError(
                "Your session has expired. Please sign in again.", code="token_expired"
            ) from exc
        except fb_auth.RevokedIdTokenError as exc:
            raise UnauthorizedError(
                "Your session was revoked. Please sign in again.", code="token_revoked"
            ) from exc
        except fb_auth.UserDisabledError as exc:
            raise UnauthorizedError(
                "This account has been disabled.", code="user_disabled"
            ) from exc
        except fb_auth.CertificateFetchError as exc:
            raise ServiceUnavailableError(
                "Could not verify sign-in right now. Try again shortly."
            ) from exc
        except (fb_auth.InvalidIdTokenError, ValueError) as exc:
            raise UnauthorizedError("Invalid authentication token.", code="invalid_token") from exc

        return AuthenticatedUser(
            uid=claims["uid"],
            email=claims.get("email"),
            email_verified=bool(claims.get("email_verified", False)),
            name=claims.get("name"),
        )


_verifier = FirebaseTokenVerifier()


def get_token_verifier() -> TokenVerifier:
    """Dependency so tests can substitute a fake verifier."""
    return _verifier


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise UnauthorizedError("Sign in to continue.", code="missing_token")
    return verifier.verify(credentials.credentials)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
