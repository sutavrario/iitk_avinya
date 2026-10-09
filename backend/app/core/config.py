"""Application settings loaded from environment variables / backend/.env.

Real environment variables take precedence over values in backend/.env.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EMULATOR_PROJECT_ID = "demo-vyaparai"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "VyaparAI"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = False
    cors_origins: str = "http://localhost:3000"

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    
    # --- Translation ----------------------------------------------------------------------
    google_cloud_api_key: SecretStr | None = None

    # --- Firebase -------------------------------------------------------------------------
    firebase_project_id: str | None = None
    firebase_storage_bucket: str | None = None
    # Path to a service-account JSON stored OUTSIDE the repo. Leave empty on Cloud Run
    # (the service's attached service account is used via Application Default Credentials).
    google_application_credentials: str | None = None

    # Local emulators: no credentials needed, nothing touches the real project.
    firebase_use_emulators: bool = False
    firebase_auth_emulator_host: str = "127.0.0.1:9099"
    firestore_emulator_host: str = "127.0.0.1:8080"
    firebase_storage_emulator_host: str = "127.0.0.1:9199"

    # --- Uploads & ingestion ---------------------------------------------------------------
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    # "tesseract" uses the local binary (free); "none" disables OCR (scans fail with a clear message).
    ocr_provider: Literal["tesseract", "none"] = "tesseract"
    ocr_languages: str = "eng"  # e.g. "eng+hin" after `brew install tesseract-lang`
    tesseract_cmd: str | None = None  # path to the binary if it isn't on PATH
    ocr_timeout_seconds: int = Field(default=60, gt=0)
    # "rules" = built-in free extractor; "llm" = reserved for Gemini (falls back to rules until configured)
    extraction_provider: Literal["rules", "llm"] = "rules"
    # "auto" = PDF text layer first, OCR only for pages without text; "ocr" = always OCR
    pdf_text_strategy: Literal["auto", "ocr"] = "auto"
    ingestion_lease_seconds: int = Field(default=600, gt=0)

    chroma_persist_dir: str = Field(default="./.chroma")

    @model_validator(mode="after")
    def _emulator_guard(self) -> "Settings":
        if self.firebase_use_emulators and self.app_env == "production":
            raise ValueError("FIREBASE_USE_EMULATORS must not be enabled in production")
        return self

    @property
    def effective_project_id(self) -> str | None:
        return EMULATOR_PROJECT_ID if self.firebase_use_emulators else self.firebase_project_id

    @property
    def effective_storage_bucket(self) -> str | None:
        if self.firebase_use_emulators:
            return f"{EMULATOR_PROJECT_ID}.appspot.com"
        return self.firebase_storage_bucket

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
