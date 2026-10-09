"""Pluggable LLM and embedding providers.

Every consumer depends on the *protocol*, not the concrete class, so the
Gemini implementation can be swapped out without touching callers.
"""

from typing import Protocol

from google import genai
from google.genai import types as genai_types

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


class EmbeddingProvider(Protocol):
    """Generate dense vectors for text chunks."""

    name: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding per input text."""
        ...


class ChatProvider(Protocol):
    """Single-turn generation from a prompt + optional system instruction."""

    name: str

    def generate(
        self,
        *,
        system_instruction: str,
        prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """Return the model's text response."""
        ...


# ---------------------------------------------------------------------------
# Gemini implementations (google-genai SDK)
# ---------------------------------------------------------------------------

_EMBEDDING_MODEL = "gemini-embedding-001"
_EMBEDDING_DIMENSIONS = 768  # default for gemini-embedding-001


class GeminiEmbeddingProvider:
    name = "gemini"
    dimensions = _EMBEDDING_DIMENSIONS

    def __init__(self) -> None:
        settings = get_settings()
        api_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required for the Gemini embedding provider.")
        self._client = genai.Client(api_key=api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # google-genai SDK supports batched embedding
        result = self._client.models.embed_content(
            model=_EMBEDDING_MODEL,
            contents=texts,  # type: ignore[arg-type]
            config=genai_types.EmbedContentConfig(
                output_dimensionality=self.dimensions,
            ),
        )
        return [list(e.values) for e in result.embeddings]  # type: ignore


class GeminiChatProvider:
    name = "gemini"

    def __init__(self) -> None:
        settings = get_settings()
        api_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required for the Gemini chat provider.")
        self._client = genai.Client(api_key=api_key)
        self._model = settings.gemini_model

    def generate(
        self,
        *,
        system_instruction: str,
        prompt: str,
        temperature: float = 0.2,
    ) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
            ),
        )
        return response.text or ""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_embedding_provider: EmbeddingProvider | None = None
_chat_provider: ChatProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = GeminiEmbeddingProvider()
    return _embedding_provider


def get_chat_provider() -> ChatProvider:
    global _chat_provider
    if _chat_provider is None:
        _chat_provider = GeminiChatProvider()
    return _chat_provider


def reset_providers() -> None:
    """For tests: reset cached singletons."""
    global _embedding_provider, _chat_provider
    _embedding_provider = None
    _chat_provider = None
