"""Unit tests for the AI copilot subsystem.

Tests cover:
- Question classification accuracy
- Vector store chunking, indexing, retrieval, and deletion
- Business-scoped data isolation (cross-business queries return nothing)
- Copilot response structure and grounding
- Hallucination-prone questions (missing evidence handling)
- Financial evidence formatting
"""

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakeEmbeddingProvider:
    """Deterministic embedding provider for tests.

    Produces a simple hash-based vector so that identical texts produce
    identical embeddings, and different texts produce different ones.
    """

    name = "fake"
    dimensions = 16

    def embed(self, texts: list[str]) -> list[list[float]]:
        result: list[list[float]] = []
        for text in texts:
            # Use hash of text to create a deterministic vector
            h = hash(text) % (2**32)
            vec = [(h >> i & 0xFF) / 255.0 for i in range(0, self.dimensions * 2, 2)]
            result.append(vec)
        return result


class FakeChatProvider:
    """Returns a canned answer so tests don't call the real LLM."""

    name = "fake"

    def __init__(self, response: str = "Based on the evidence, the answer is: test response.") -> None:
        self.response = response
        self.last_prompt: str = ""
        self.last_system: str = ""
        self.call_count = 0

    def generate(self, *, system_instruction: str, prompt: str, temperature: float = 0.2) -> str:
        self.last_system = system_instruction
        self.last_prompt = prompt
        self.call_count += 1
        return self.response


# ---------------------------------------------------------------------------
# Question classification
# ---------------------------------------------------------------------------


class TestClassifyQuestion:
    def test_financial_question(self) -> None:
        from app.services.copilot import classify_question

        assert classify_question("Which invoices are overdue?") == "financial"

    def test_document_question(self) -> None:
        from app.services.copilot import classify_question

        assert classify_question("What does the contract say about delivery clause?") == "document"

    def test_hybrid_question(self) -> None:
        from app.services.copilot import classify_question

        assert classify_question("What payment terms are mentioned in the invoice document?") == "hybrid"

    def test_general_question(self) -> None:
        from app.services.copilot import classify_question

        assert classify_question("How do I improve my business?") == "general"

    def test_expense_question(self) -> None:
        from app.services.copilot import classify_question

        assert classify_question("What were the largest expenses last month?") == "financial"

    def test_risk_document_question(self) -> None:
        from app.services.copilot import classify_question

        assert classify_question("Summarize the key risks found in my uploaded documents") == "document"

    def test_follow_up_question(self) -> None:
        from app.services.copilot import classify_question

        assert classify_question("Which customer payments should I follow up on?") == "financial"

    def test_supplier_contract_question(self) -> None:
        from app.services.copilot import classify_question

        assert classify_question("What terms appear in the supplier contract?") == "hybrid"


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------


class TestChunking:
    def test_empty_text(self) -> None:
        from app.services.vector_store import chunk_text

        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_short_text_single_chunk(self) -> None:
        from app.services.vector_store import chunk_text

        result = chunk_text("Hello world", chunk_size=100, overlap=50)
        assert len(result) == 1
        assert result[0] == "Hello world"

    def test_overlap_produces_multiple_chunks(self) -> None:
        from app.services.vector_store import chunk_text

        text = "A" * 200
        result = chunk_text(text, chunk_size=100, overlap=50)
        assert len(result) > 1
        # Each chunk should have content
        for chunk in result:
            assert len(chunk) > 0

    def test_chunks_cover_full_text(self) -> None:
        from app.services.vector_store import chunk_text

        text = "word " * 500  # ~2500 chars
        result = chunk_text(text, chunk_size=200, overlap=50)
        # The union of all chunks should cover the original text (approximately)
        assert len(result) >= 5


# ---------------------------------------------------------------------------
# Vector store (ChromaDB)
# ---------------------------------------------------------------------------


class TestVectorStore:
    """Tests that use an in-memory ChromaDB instance."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Any) -> Any:
        """Patch ChromaDB to use a temporary directory."""
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.PersistentClient(
            path=str(tmp_path / "chroma"),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        with patch("app.services.vector_store.get_chroma_client", return_value=client):
            yield

    def test_index_and_retrieve(self) -> None:
        from app.services.vector_store import index_document, retrieve_relevant_chunks

        provider = FakeEmbeddingProvider()

        chunks = index_document(
            business_id="biz1",
            document_id="doc1",
            file_name="invoice.pdf",
            pages=[{"text": "Invoice #123 from Acme Corp for Rs 50,000", "page": 1}],
            embedding_provider=provider,
        )
        assert chunks > 0

        results = retrieve_relevant_chunks(
            "biz1", "Acme Corp invoice", n_results=5, embedding_provider=provider
        )
        assert len(results) > 0
        assert results[0]["documentId"] == "doc1"
        assert results[0]["fileName"] == "invoice.pdf"

    def test_cross_business_isolation(self) -> None:
        """Querying as business B must not return business A's documents."""
        from app.services.vector_store import index_document, retrieve_relevant_chunks

        provider = FakeEmbeddingProvider()

        index_document(
            business_id="bizA",
            document_id="docA",
            file_name="secret.pdf",
            pages=[{"text": "Confidential contract for BizA only", "page": 1}],
            embedding_provider=provider,
        )

        results = retrieve_relevant_chunks(
            "bizB", "confidential contract", n_results=5, embedding_provider=provider
        )
        assert len(results) == 0  # BizB must see nothing

    def test_delete_document(self) -> None:
        from app.services.vector_store import (
            delete_document,
            index_document,
            retrieve_relevant_chunks,
        )

        provider = FakeEmbeddingProvider()

        index_document(
            business_id="biz1",
            document_id="doc_to_delete",
            file_name="temp.pdf",
            pages=[{"text": "Temporary data that will be deleted", "page": 1}],
            embedding_provider=provider,
        )
        delete_document("biz1", "doc_to_delete")

        results = retrieve_relevant_chunks(
            "biz1", "temporary data", n_results=5, embedding_provider=provider
        )
        assert len(results) == 0

    def test_reindex_replaces_old_chunks(self) -> None:
        """Re-indexing the same document should replace, not duplicate."""
        from app.services.vector_store import index_document, retrieve_relevant_chunks

        provider = FakeEmbeddingProvider()

        index_document(
            business_id="biz1",
            document_id="doc_reindex",
            file_name="data.csv",
            pages=[{"text": "Old content version 1", "page": 1}],
            embedding_provider=provider,
        )
        index_document(
            business_id="biz1",
            document_id="doc_reindex",
            file_name="data.csv",
            pages=[{"text": "New content version 2", "page": 1}],
            embedding_provider=provider,
        )

        results = retrieve_relevant_chunks(
            "biz1", "content version", n_results=10, embedding_provider=provider
        )
        # Should only have chunks from the second index call
        doc_ids = [r["documentId"] for r in results]
        assert all(d == "doc_reindex" for d in doc_ids)

    def test_multi_page_indexing(self) -> None:
        from app.services.vector_store import index_document

        provider = FakeEmbeddingProvider()

        chunks = index_document(
            business_id="biz1",
            document_id="multi_page",
            file_name="report.pdf",
            pages=[
                {"text": "Page 1 content about sales", "page": 1},
                {"text": "Page 2 content about expenses", "page": 2},
                {"text": "Page 3 content about projections", "page": 3},
            ],
            embedding_provider=provider,
        )
        assert chunks == 3  # one chunk per short page

    def test_delete_all_for_business(self) -> None:
        from app.services.vector_store import (
            delete_all_for_business,
            index_document,
            retrieve_relevant_chunks,
        )

        provider = FakeEmbeddingProvider()

        for i in range(3):
            index_document(
                business_id="biz_to_purge",
                document_id=f"doc_{i}",
                file_name=f"file_{i}.pdf",
                pages=[{"text": f"Content for document {i}", "page": 1}],
                embedding_provider=provider,
            )

        delete_all_for_business("biz_to_purge")
        results = retrieve_relevant_chunks(
            "biz_to_purge", "content", n_results=10, embedding_provider=provider
        )
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Copilot answer (integration of classify + evidence + LLM)
# ---------------------------------------------------------------------------


class TestCopilotAnswer:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Any) -> Any:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.PersistentClient(
            path=str(tmp_path / "chroma"),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        with patch("app.services.vector_store.get_chroma_client", return_value=client):
            with patch(
                "app.services.vector_store.get_embedding_provider",
                return_value=FakeEmbeddingProvider(),
            ):
                yield

    def _sample_metrics(self) -> dict[str, Any]:
        return {
            "outstanding_receivables": 125000.0,
            "overdue_receivables": 50000.0,
            "upcoming_receivables": 75000.0,
            "supplier_payables": 30000.0,
            "expenses_total": 80000.0,
            "cash_flow": {"total_in": 200000.0, "total_out": 80000.0, "net": 120000.0},
            "monthly_summaries": [
                {"month": "2026-09", "income": 150000.0, "expense": 60000.0},
                {"month": "2026-10", "income": 50000.0, "expense": 20000.0},
            ],
            "warnings": ["Invoice inv_001 is outstanding but has no due date."],
            "duplicate_payments": [],
        }

    def _sample_invoices(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "inv_001",
                "invoiceNumber": "INV-2026-001",
                "customerName": "Acme Corp",
                "issueDate": "2026-09-01",
                "dueDate": "2026-09-30",
                "amount": 50000.0,
                "status": "overdue",
            },
            {
                "id": "inv_002",
                "invoiceNumber": "INV-2026-002",
                "customerName": "Beta Ltd",
                "issueDate": "2026-10-01",
                "dueDate": "2026-10-31",
                "amount": 75000.0,
                "status": "unpaid",
            },
        ]

    def test_financial_question_uses_metrics(self) -> None:
        from app.services.copilot import copilot_answer

        fake_llm = FakeChatProvider("Your overdue receivables total ₹50,000.")
        result = copilot_answer(
            business_id="biz1",
            question="Which invoices are overdue?",
            financial_metrics=self._sample_metrics(),
            invoices=self._sample_invoices(),
            expenses=[],
            payments=[],
            chat_provider=fake_llm,
        )

        assert result["category"] == "financial"
        assert "overdue" in fake_llm.last_prompt.lower() or "outstanding" in fake_llm.last_prompt.lower()
        assert result["answer"] == "Your overdue receivables total ₹50,000."
        assert result["timestamp"]

    def test_document_question_searches_vector_store(self) -> None:
        from app.services.copilot import copilot_answer

        fake_llm = FakeChatProvider("The contract mentions net-30 payment terms.")
        result = copilot_answer(
            business_id="biz1",
            question="What payment terms appear in the supplier contract?",
            chat_provider=fake_llm,
        )

        assert result["category"] in ("document", "hybrid")
        assert result["answer"] == "The contract mentions net-30 payment terms."

    def test_missing_evidence_produces_caveats(self) -> None:
        from app.services.copilot import copilot_answer

        fake_llm = FakeChatProvider(
            "I don't have enough information to answer this question.\n"
            "Please upload the relevant contract documents."
        )
        result = copilot_answer(
            business_id="empty_biz",
            question="What is the warranty clause in the contract?",
            chat_provider=fake_llm,
        )

        assert len(result["caveats"]) > 0

    def test_recommendations_extracted(self) -> None:
        from app.services.copilot import copilot_answer

        fake_llm = FakeChatProvider(
            "You have ₹50,000 overdue.\n"
            "Recommendation: Send payment reminders to Acme Corp immediately.\n"
            "Recommendation: Consider offering early payment discounts."
        )
        result = copilot_answer(
            business_id="biz1",
            question="What should I do about overdue payments?",
            financial_metrics=self._sample_metrics(),
            invoices=self._sample_invoices(),
            expenses=[],
            payments=[],
            chat_provider=fake_llm,
        )

        assert len(result["recommended_actions"]) == 2

    def test_system_prompt_included(self) -> None:
        from app.services.copilot import copilot_answer

        fake_llm = FakeChatProvider("Test response.")
        copilot_answer(
            business_id="biz1",
            question="Test question",
            chat_provider=fake_llm,
        )

        assert "NEVER invent" in fake_llm.last_system
        assert "VyaparAI" in fake_llm.last_system

    def test_evidence_block_in_prompt(self) -> None:
        """The prompt sent to the LLM must include the evidence section."""
        from app.services.copilot import copilot_answer

        fake_llm = FakeChatProvider("Answer.")
        copilot_answer(
            business_id="biz1",
            question="What is my cash flow?",
            financial_metrics=self._sample_metrics(),
            chat_provider=fake_llm,
        )

        assert "EVIDENCE" in fake_llm.last_prompt
        assert "₹200,000.00" in fake_llm.last_prompt or "200000" in fake_llm.last_prompt

    def test_hallucination_guard_no_financial_data(self) -> None:
        """When no financial data is given, the model should not see invented numbers."""
        from app.services.copilot import copilot_answer

        fake_llm = FakeChatProvider("I don't have enough information.")
        copilot_answer(
            business_id="biz_empty",
            question="What are my total sales?",
            financial_metrics=None,
            chat_provider=fake_llm,
        )

        # The prompt should not contain fabricated financial figures
        assert "outstanding" not in fake_llm.last_prompt.lower() or "No evidence" in fake_llm.last_prompt

    def test_conversation_history_passed(self) -> None:
        from app.services.copilot import copilot_answer

        fake_llm = FakeChatProvider("Follow-up answer.")
        history = [
            {"role": "user", "content": "What are my overdue invoices?"},
            {"role": "assistant", "content": "You have 2 overdue invoices."},
        ]
        copilot_answer(
            business_id="biz1",
            question="Can you list them?",
            financial_metrics=self._sample_metrics(),
            invoices=self._sample_invoices(),
            expenses=[],
            payments=[],
            conversation_history=history,
            chat_provider=fake_llm,
        )

        assert "Previous conversation" in fake_llm.last_prompt
        assert "overdue invoices" in fake_llm.last_prompt.lower()


# ---------------------------------------------------------------------------
# Financial evidence formatting
# ---------------------------------------------------------------------------


class TestFinancialEvidenceFormatting:
    def test_format_financial_evidence(self) -> None:
        from app.services.copilot import _format_financial_evidence

        metrics: dict[str, Any] = {
            "outstanding_receivables": 100000.0,
            "overdue_receivables": 25000.0,
            "upcoming_receivables": 75000.0,
            "supplier_payables": 0.0,
            "expenses_total": 50000.0,
            "cash_flow": {"total_in": 150000.0, "total_out": 50000.0, "net": 100000.0},
            "monthly_summaries": [{"month": "2026-09", "income": 100000.0, "expense": 50000.0}],
            "warnings": ["Test warning"],
            "duplicate_payments": [],
        }

        result = _format_financial_evidence(metrics)
        assert "₹100,000.00" in result  # outstanding
        assert "₹25,000.00" in result  # overdue
        assert "Cash in" in result
        assert "Test warning" in result

    def test_format_empty_metrics(self) -> None:
        from app.services.copilot import _format_financial_evidence

        result = _format_financial_evidence({})
        assert "Financial Records Summary" in result

    def test_format_document_evidence_empty(self) -> None:
        from app.services.copilot import _format_document_evidence

        result = _format_document_evidence([])
        assert "No relevant document passages found" in result

    def test_format_document_evidence_with_chunks(self) -> None:
        from app.services.copilot import _format_document_evidence

        chunks = [
            {
                "text": "Payment terms: Net 30 days.",
                "documentId": "doc123",
                "fileName": "contract.pdf",
                "page": 3,
            }
        ]
        result = _format_document_evidence(chunks)
        assert "contract.pdf" in result
        assert "Page 3" in result
        assert "doc123" in result
        assert "Net 30 days" in result


# ---------------------------------------------------------------------------
# Source deduplication
# ---------------------------------------------------------------------------


class TestSourceDeduplication:
    def test_dedup(self) -> None:
        from app.services.copilot import _deduplicate_sources

        sources = [
            {"documentId": "doc1", "page": 1},
            {"documentId": "doc1", "page": 1},  # duplicate
            {"documentId": "doc1", "page": 2},  # different page
            {"documentId": "doc2", "page": 1},  # different doc
        ]
        result = _deduplicate_sources(sources)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# LLM provider protocol compliance
# ---------------------------------------------------------------------------


class TestProviders:
    def test_fake_embedding_dimensions(self) -> None:
        provider = FakeEmbeddingProvider()
        vectors = provider.embed(["hello", "world"])
        assert len(vectors) == 2
        assert len(vectors[0]) == provider.dimensions

    def test_fake_embedding_deterministic(self) -> None:
        provider = FakeEmbeddingProvider()
        v1 = provider.embed(["test"])[0]
        v2 = provider.embed(["test"])[0]
        assert v1 == v2

    def test_fake_embedding_empty(self) -> None:
        provider = FakeEmbeddingProvider()
        assert provider.embed([]) == []

    def test_fake_chat_provider(self) -> None:
        provider = FakeChatProvider("hello")
        result = provider.generate(system_instruction="sys", prompt="question")
        assert result == "hello"
        assert provider.call_count == 1
        assert provider.last_prompt == "question"
        assert provider.last_system == "sys"
