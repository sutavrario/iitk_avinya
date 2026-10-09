"""ChromaDB vector store for document chunks.

Stores text chunks with metadata (businessId, documentId, fileName, page/sheet, chunkIndex).
All retrieval is scoped to a single businessId via Chroma's `where` filter.

Local development: ChromaDB persists to `CHROMA_PERSIST_DIR` (default `./.chroma`).
Production: point `CHROMA_PERSIST_DIR` at a persistent volume (e.g. a GCE disk mounted
at `/data/chroma`), or switch to `chromadb.HttpClient(host=..., port=...)` for a
standalone Chroma server behind Cloud Run.
"""

from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.llm_providers import EmbeddingProvider, get_embedding_provider

logger = get_logger(__name__)

COLLECTION_NAME = "document_chunks"
CHUNK_SIZE = 800  # characters; overlap is half
CHUNK_OVERLAP = 400


# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_chroma_client: Any = None


def get_chroma_client() -> Any:
    global _chroma_client
    if _chroma_client is None:
        settings = get_settings()
        _chroma_client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info("ChromaDB initialised at %s", settings.chroma_persist_dir)
    return _chroma_client


def reset_chroma_client() -> None:
    """For tests: reset the singleton."""
    global _chroma_client
    _chroma_client = None


def _get_or_create_collection(client: Any) -> Any:
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks of roughly `chunk_size` characters."""
    if not text.strip():
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks


# ---------------------------------------------------------------------------
# Index (add / update / delete)
# ---------------------------------------------------------------------------


def index_document(
    business_id: str,
    document_id: str,
    file_name: str,
    pages: list[dict[str, Any]],
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> int:
    """Index a document's extracted text into ChromaDB.

    `pages` is a list of dicts with keys: `text`, `page` (int, 1-based),
    and optionally `sheet_name`.

    Returns the number of chunks stored.
    """
    provider = embedding_provider or get_embedding_provider()
    client = get_chroma_client()
    collection = _get_or_create_collection(client)

    # Remove any previous chunks for this document first (idempotent re-index).
    delete_document(business_id, document_id)

    all_chunks: list[str] = []
    all_ids: list[str] = []
    all_meta: list[dict[str, Any]] = []

    for page_info in pages:
        text = page_info.get("text", "")
        page_num = page_info.get("page", 1)
        sheet_name = page_info.get("sheet_name")
        chunks = chunk_text(text)

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_p{page_num}_c{idx}"
            meta: dict[str, Any] = {
                "businessId": business_id,
                "documentId": document_id,
                "fileName": file_name,
                "page": page_num,
                "chunkIndex": idx,
            }
            if sheet_name:
                meta["sheetName"] = sheet_name
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_meta.append(meta)

    if not all_chunks:
        return 0

    # Embed in batches of 96 (Gemini API limit)
    batch_size = 96
    all_embeddings: list[list[float]] = []
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        all_embeddings.extend(provider.embed(batch))

    collection.add(
        ids=all_ids,
        embeddings=all_embeddings,
        documents=all_chunks,
        metadatas=all_meta,
    )

    logger.info(
        "Indexed %d chunks for document %s (business %s)",
        len(all_chunks),
        document_id,
        business_id,
    )
    return len(all_chunks)


def delete_document(business_id: str, document_id: str) -> None:
    """Remove all chunks for a specific document."""
    client = get_chroma_client()
    collection = _get_or_create_collection(client)
    # ChromaDB requires `$and` for compound where filters.
    existing = collection.get(
        where={"$and": [{"businessId": business_id}, {"documentId": document_id}]},
    )
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
        logger.info("Deleted %d chunks for document %s", len(existing["ids"]), document_id)


def delete_all_for_business(business_id: str) -> None:
    """Remove all chunks for an entire business (e.g. account deletion)."""
    client = get_chroma_client()
    collection = _get_or_create_collection(client)
    existing = collection.get(where={"businessId": business_id})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def retrieve_relevant_chunks(
    business_id: str,
    query: str,
    *,
    n_results: int = 8,
    embedding_provider: EmbeddingProvider | None = None,
) -> list[dict[str, Any]]:
    """Semantic search scoped to one business.

    Returns a list of dicts with keys: `text`, `documentId`, `fileName`,
    `page`, `chunkIndex`, `distance`.
    """
    provider = embedding_provider or get_embedding_provider()
    client = get_chroma_client()
    collection = _get_or_create_collection(client)

    query_embedding = provider.embed([query])[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where={"businessId": business_id},
    )

    chunks: list[dict[str, Any]] = []
    if not results["ids"] or not results["ids"][0]:
        return chunks

    ids = results["ids"][0]
    documents = results["documents"][0] if results["documents"] else [""] * len(ids)
    metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
    distances = results["distances"][0] if results["distances"] else [0.0] * len(ids)

    for doc_text, meta, dist in zip(documents, metadatas, distances, strict=False):
        chunks.append(
            {
                "text": doc_text,
                "documentId": meta.get("documentId", ""),
                "fileName": meta.get("fileName", ""),
                "page": meta.get("page"),
                "sheetName": meta.get("sheetName"),
                "chunkIndex": meta.get("chunkIndex"),
                "distance": dist,
            }
        )
    return chunks
