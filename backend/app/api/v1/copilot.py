"""AI Copilot API routes.

POST /businesses/{businessId}/copilot/ask      — ask a question
GET  /businesses/{businessId}/copilot/conversations — list conversations
GET  /businesses/{businessId}/copilot/conversations/{id}/messages — get messages
POST /businesses/{businessId}/copilot/index/{documentId} — index a document
DELETE /businesses/{businessId}/copilot/index/{documentId} — remove from index
"""

from datetime import date
from typing import Any

from fastapi import APIRouter

from app.api.v1.deps import Db
from app.repositories import collections as col
from app.repositories import conversations as conv_repo
from app.repositories import records as records_repo
from app.repositories import users as users_repo
from app.schemas.copilot import (
    ConversationOut,
    CopilotMessageIn,
    CopilotMessageOut,
    IndexDocumentOut,
    SourceReference,
)
from app.schemas.records import ExpenseOut, InvoiceOut, PaymentOut
from app.services.authorization import CanEdit, CanView
from app.services.copilot import copilot_answer
from app.services.financial_engine import compute_financial_metrics
from app.services.invoices import expense_to_api, invoice_to_api, payment_to_api
from app.services.translation import get_translation_service
from app.services.vector_store import delete_document, index_document

router = APIRouter(prefix="/businesses/{business_id}/copilot", tags=["copilot"])


@router.post("/ask", response_model=CopilotMessageOut)
def ask_copilot(body: CopilotMessageIn, access: CanView, db: Db) -> CopilotMessageOut:
    """Ask the AI copilot a question about your business data."""
    print("DEBUG body language:", body.language)
    today = date.today()

    # Fetch structured business data for the financial engine
    invoice_docs = records_repo.list_records(db, col.INVOICES, access, order_by="issueDate")
    invoices_api = [invoice_to_api(d, today) for d in invoice_docs]
    invoices = [InvoiceOut.model_validate(d) for d in invoices_api]

    expense_docs = records_repo.list_records(db, col.EXPENSES, access, order_by="date")
    expenses_api = [expense_to_api(d) for d in expense_docs]
    expenses = [ExpenseOut.model_validate(d) for d in expenses_api]

    payment_docs = records_repo.list_records(db, col.PAYMENTS, access, order_by="date")
    payments_api = [payment_to_api(d) for d in payment_docs]
    payments = [PaymentOut.model_validate(d) for d in payments_api]

    # Fetch active action plans
    all_action_plans = records_repo.list_records(
        db, 
        col.ACTION_PLANS, 
        access, 
        order_by="createdAt"
    )
    action_plan_docs = [ap for ap in all_action_plans if ap.get("status") in ("active", "dismissed")]
    # We can pass them mostly raw, or we can use the schema validation. They are dicts.
    action_plans = [
        {
            "id": ap.get("id"),
            "title": ap.get("title", ""),
            "description": ap.get("description", ""),
            "type": ap.get("type", "info"),
            "priority": ap.get("priority", "medium"),
            "reason": ap.get("reason", ""),
            "status": ap.get("status", "active"),
            "suggestedDeadline": ap.get("suggestedDeadline"),
            "relatedRecordIds": ap.get("relatedRecordIds", []),
        } for ap in action_plan_docs
    ]

    # Compute verified financial metrics (no LLM involved)
    metrics = compute_financial_metrics(invoices, expenses, payments, today)
    metrics_dict = metrics.model_dump()

    # Get conversation history if resuming
    conversation_history: list[dict[str, str]] | None = None
    conversation_id = body.conversation_id
    if conversation_id:
        conv = conv_repo.get_conversation(db, conversation_id, access.business_id)
        if conv:
            messages = conv_repo.get_messages(db, conversation_id)
            conversation_history = [
                {"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages
            ]
    else:
        # Create a new conversation
        title = body.question[:80] + ("..." if len(body.question) > 80 else "")
        conv = conv_repo.create_conversation(db, access.business_id, access.user.uid, title)
        conversation_id = conv["id"]
        
    translation_service = get_translation_service()
    
    # Fetch user preferences reliably from the DB instead of relying on the client
    user_data = users_repo.ensure_user(db, access.user)
    prefs = user_data.get("preferences", {})
    lang = prefs.get("copilotLanguage", "en")
    always_translate = prefs.get("alwaysTranslateReplies", False)
    
    # If the user asks in English but didn't toggle "always translate", 
    # we might technically want to reply in English. But to avoid confusion 
    # (since the UI badge says "Replies in Bengali"), we will default to 
    # translating to their chosen language unless they explicitly have it set to 'en'.
    
    process_question = body.question
    
    if lang != "en":
        process_question = translation_service.translate_text(
            text=body.question,
            target_language="en",
            source_language=lang
        )

    # Run the RAG pipeline
    result = copilot_answer(
        business_id=access.business_id,
        question=process_question,
        financial_metrics=metrics_dict,
        invoices=invoices_api,
        expenses=expenses_api,
        payments=payments_api,
        action_plan=action_plans,
        conversation_history=conversation_history,
    )
    
    final_answer = result["answer"]
    final_caveats = result.get("caveats", [])
    final_actions = result.get("recommended_actions", [])
    if lang != "en":
        final_answer = translation_service.translate_text(
            text=final_answer,
            target_language=lang,
            source_language="en"
        )
        final_caveats = [
            translation_service.translate_text(text=c, target_language=lang, source_language="en")
            for c in final_caveats
        ]
        final_actions = [
            translation_service.translate_text(text=a, target_language=lang, source_language="en")
            for a in final_actions
        ]

    # Save messages to conversation history
    conv_repo.add_message(db, conversation_id, "user", body.question)
    conv_repo.add_message(
        db,
        conversation_id,
        "assistant",
        final_answer,
        category=result.get("category"),
        sources=result.get("sources"),
    )

    return CopilotMessageOut(
        answer=final_answer,
        category=result["category"],
        sources=[
            SourceReference(
                document_id=s.get("documentId"),
                file_name=s.get("fileName"),
                page=s.get("page"),
                sheet_name=s.get("sheetName"),
            )
            for s in result.get("sources", [])
        ],
        caveats=final_caveats,
        recommended_actions=final_actions,
        conversation_id=conversation_id,
        timestamp=result["timestamp"],
    )


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(access: CanView, db: Db) -> list[ConversationOut]:
    """List the user's copilot conversations for this business."""
    conversations = conv_repo.list_conversations(db, access.business_id)
    return [
        ConversationOut(
            id=c["id"],
            title=c.get("title", "Untitled"),
            message_count=c.get("messageCount", 0),
            created_at=c["createdAt"],
            updated_at=c["updatedAt"],
        )
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: str,
    access: CanView,
    db: Db,
) -> list[dict[str, Any]]:
    """Get all messages in a conversation."""
    conv = conv_repo.get_conversation(db, conversation_id, access.business_id)
    if not conv:
        from app.core.errors import NotFoundError

        raise NotFoundError("Conversation not found.")
    return conv_repo.get_messages(db, conversation_id)


@router.post("/index/{document_id}", response_model=IndexDocumentOut)
def index_document_endpoint(document_id: str, access: CanEdit, db: Db) -> IndexDocumentOut:
    """Index an uploaded document into the vector store for RAG retrieval."""
    # Get the document metadata from Firestore
    doc_snap = db.collection(col.UPLOADED_DOCUMENTS).document(document_id).get()
    doc_data = doc_snap.to_dict() if doc_snap.exists else None
    if not doc_data or doc_data.get("businessId") != access.business_id:
        from app.core.errors import NotFoundError

        raise NotFoundError("Document not found.")

    file_name = doc_data.get("originalName", "unknown")

    # Get the extracted text from subcollection or raw text field
    pages: list[dict[str, Any]] = []
    extracted = (
        db.collection(col.UPLOADED_DOCUMENTS)
        .document(document_id)
        .collection(col.EXTRACTED_RECORDS)
        .stream()
    )
    # If there are extracted records, use the raw text stored with them
    for rec in extracted:
        rec_data = rec.to_dict() or {}
        source = rec_data.get("source", {})
        text_snippet = source.get("snippet", "")
        raw_values = rec_data.get("rawValues", {})
        # Build text from all available raw values
        text_parts = [text_snippet]
        for _field, value in raw_values.items():
            if isinstance(value, str):
                text_parts.append(value)
        pages.append(
            {
                "text": " ".join(text_parts),
                "page": source.get("page", source.get("rowNumber", 1)),
                "sheet_name": source.get("sheetName"),
            }
        )

    # Also check if there's a `parsedText` field on the document itself
    parsed_text = doc_data.get("parsedText")
    if parsed_text and isinstance(parsed_text, str):
        pages.append({"text": parsed_text, "page": 1})

    # If no text is available, try the raw pages stored during ingestion
    raw_pages = doc_data.get("rawPages", [])
    if raw_pages and isinstance(raw_pages, list):
        for rp in raw_pages:
            if isinstance(rp, dict) and rp.get("text"):
                pages.append(
                    {
                        "text": rp["text"],
                        "page": rp.get("page", 1),
                    }
                )

    if not pages:
        from app.core.errors import AppError

        raise AppError(
            "No text content found for this document. "
            "Make sure the document has been processed first.",
            code="no_text_content",
        )

    chunks_count = index_document(
        business_id=access.business_id,
        document_id=document_id,
        file_name=file_name,
        pages=pages,
    )

    return IndexDocumentOut(
        document_id=document_id,
        chunks_indexed=chunks_count,
        message=f"Indexed {chunks_count} chunks from '{file_name}'.",
    )


@router.delete("/index/{document_id}")
def delete_document_index(document_id: str, access: CanEdit, db: Db) -> dict[str, Any]:
    """Remove a document from the vector store index."""
    delete_document(access.business_id, document_id)
    return {"message": f"Document {document_id} removed from index."}
