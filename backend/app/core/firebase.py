"""Firebase Admin SDK bootstrap (server-side only — never shipped to the browser).

Credential resolution, in order:
1. Emulators (FIREBASE_USE_EMULATORS=true): anonymous credentials, demo project, local hosts.
2. GOOGLE_APPLICATION_CREDENTIALS: path to a service-account JSON kept outside the repo.
3. Application Default Credentials (Cloud Run service account, or
   `gcloud auth application-default login`).
"""

import os
import json
import threading
from typing import Any

import firebase_admin
import google.auth.credentials
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore import Client as FirestoreClient
from google.cloud.storage import Bucket

from app.core.config import Settings, get_settings
from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)
_lock = threading.Lock()
_app: firebase_admin.App | None = None


class _EmulatorCredential(credentials.Base):  # type: ignore[misc]
    """Anonymous credentials for local emulators (they don't validate credentials)."""

    def get_credential(self) -> google.auth.credentials.Credentials:
        return google.auth.credentials.AnonymousCredentials()  # type: ignore[no-untyped-call]


def _configure_emulator_env(settings: Settings) -> None:
    # The Admin SDK and Google Cloud clients read these process env vars.
    os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = settings.firebase_auth_emulator_host
    os.environ["FIRESTORE_EMULATOR_HOST"] = settings.firestore_emulator_host
    os.environ["STORAGE_EMULATOR_HOST"] = f"http://{settings.firebase_storage_emulator_host}"


def get_firebase_app() -> firebase_admin.App:
    global _app
    if _app is not None:
        return _app
    with _lock:
        if _app is not None:
            return _app
        settings = get_settings()
        project_id = settings.effective_project_id
        if not project_id:
            raise ServiceUnavailableError(
                "Firebase is not configured on the server (FIREBASE_PROJECT_ID is missing).",
                code="firebase_not_configured",
            )

        cred: credentials.Base
        if settings.firebase_use_emulators:
            _configure_emulator_env(settings)
            cred = _EmulatorCredential()
            logger.warning("Firebase Admin is using LOCAL EMULATORS (project %s)", project_id)
        elif settings.google_application_credentials_json:
            try:
                cert_dict = json.loads(settings.google_application_credentials_json.get_secret_value())
                cred = credentials.Certificate(cert_dict)
            except Exception as exc:
                raise ServiceUnavailableError(
                    "Firebase JSON credentials could not be parsed. Check GOOGLE_APPLICATION_CREDENTIALS_JSON.",
                    code="firebase_credentials_invalid",
                ) from exc
        elif settings.google_application_credentials:
            try:
                cred = credentials.Certificate(settings.google_application_credentials)
            except (OSError, ValueError) as exc:
                # Never log the file contents; the path alone is enough to debug.
                raise ServiceUnavailableError(
                    "Firebase service-account file could not be loaded. Check "
                    "GOOGLE_APPLICATION_CREDENTIALS.",
                    code="firebase_credentials_invalid",
                ) from exc
        else:
            cred = credentials.ApplicationDefault()

        options: dict[str, Any] = {"projectId": project_id}
        if bucket := settings.effective_storage_bucket:
            options["storageBucket"] = bucket
        _app = firebase_admin.initialize_app(cred, options)
        logger.info("Firebase Admin initialised for project %s", project_id)
        return _app


def get_db() -> FirestoreClient:
    """FastAPI dependency: Firestore client."""
    client: FirestoreClient = firestore.client(get_firebase_app())
    return client


def get_bucket() -> Bucket:
    """FastAPI dependency: default Cloud Storage bucket."""
    app = get_firebase_app()
    if not get_settings().effective_storage_bucket:
        raise ServiceUnavailableError(
            "File storage is not configured (FIREBASE_STORAGE_BUCKET is missing).",
            code="storage_not_configured",
        )
    return storage.bucket(app=app)
