"""Conversation repository — stores AI copilot chat history in Firestore.

Collection structure:
  conversations/{conversationId}
    ├── businessId, userId, title, messageCount, createdAt, updatedAt
    └── messages/{messageId}
        └── role, content, category, sources, timestamp
"""

from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore_v1 import FieldFilter

from app.repositories import collections as col

MAX_CONVERSATIONS = 50


def create_conversation(
    db: FirestoreClient,
    business_id: str,
    user_id: str,
    title: str,
) -> dict[str, Any]:
    """Create a new conversation document."""
    now = datetime.now(UTC)
    doc = {
        "businessId": business_id,
        "userId": user_id,
        "title": title,
        "messageCount": 0,
        "createdAt": now,
        "updatedAt": now,
    }
    ref = db.collection(col.CONVERSATIONS).document()
    ref.set(doc)
    return {**doc, "id": ref.id}


def get_conversation(
    db: FirestoreClient,
    conversation_id: str,
    business_id: str,
) -> dict[str, Any] | None:
    """Get a conversation, or None if it doesn't exist / belongs to another business."""
    snap = db.collection(col.CONVERSATIONS).document(conversation_id).get()
    data = snap.to_dict() if snap.exists else None
    if not data or data.get("businessId") != business_id:
        return None
    return {**data, "id": snap.id}


def list_conversations(
    db: FirestoreClient,
    business_id: str,
    limit: int = MAX_CONVERSATIONS,
) -> list[dict[str, Any]]:
    """List conversations for a business, newest first."""
    query = (
        db.collection(col.CONVERSATIONS)
        .where(filter=FieldFilter("businessId", "==", business_id))
        .order_by("updatedAt", direction="DESCENDING")
        .limit(limit)
    )
    return [{**(s.to_dict() or {}), "id": s.id} for s in query.stream()]


def add_message(
    db: FirestoreClient,
    conversation_id: str,
    role: str,
    content: str,
    category: str | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Append a message to a conversation and update the conversation metadata."""
    now = datetime.now(UTC)
    msg: dict[str, Any] = {
        "role": role,
        "content": content,
        "timestamp": now,
    }
    if category:
        msg["category"] = category
    if sources:
        msg["sources"] = sources

    # Add message to subcollection
    conv_ref = db.collection(col.CONVERSATIONS).document(conversation_id)
    msg_ref = conv_ref.collection(col.CONVERSATION_MESSAGES).document()
    msg_ref.set(msg)

    # Update conversation metadata
    from google.cloud.firestore_v1 import transforms

    conv_ref.update(
        {
            "messageCount": transforms.Increment(1),
            "updatedAt": now,
        }
    )

    return {**msg, "id": msg_ref.id}


def get_messages(
    db: FirestoreClient,
    conversation_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get messages for a conversation, oldest first."""
    query = (
        db.collection(col.CONVERSATIONS)
        .document(conversation_id)
        .collection(col.CONVERSATION_MESSAGES)
        .order_by("timestamp")
        .limit(limit)
    )
    return [{**(s.to_dict() or {}), "id": s.id} for s in query.stream()]
