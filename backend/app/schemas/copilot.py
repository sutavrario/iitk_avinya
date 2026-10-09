"""Pydantic schemas for the AI Copilot API."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel, InputModel


class CopilotMessageIn(InputModel):
    """User's question to the copilot."""

    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None  # resume an existing conversation
    language: str | None = None


class SourceReference(BaseModel):
    document_id: str | None = None
    file_name: str | None = None
    page: int | None = None
    sheet_name: str | None = None


class CopilotMessageOut(ApiModel):
    """Copilot's structured response."""

    answer: str
    category: str  # financial | document | hybrid | general
    sources: list[SourceReference] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    conversation_id: str
    timestamp: datetime


class ConversationOut(ApiModel):
    """Summary of a conversation."""

    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class IndexDocumentOut(ApiModel):
    """Result of indexing a document into the vector store."""

    document_id: str
    chunks_indexed: int
    message: str
