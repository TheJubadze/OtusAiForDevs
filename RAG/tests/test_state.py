"""
Tests for RAG state definitions.
"""

import pytest
from rag.state import RAGState, Document


class TestDocument:
    """Tests for Document TypedDict."""

    def test_document_creation(self):
        """Test creating a Document."""
        doc = Document(
            content="Test content",
            source="test.md",
            relevance_score=0.95,
        )

        assert doc["content"] == "Test content"
        assert doc["source"] == "test.md"
        assert doc["relevance_score"] == 0.95

    def test_document_optional_score(self):
        """Test Document with None relevance_score."""
        doc = Document(
            content="Test content",
            source="test.md",
            relevance_score=None,
        )

        assert doc["relevance_score"] is None


class TestRAGState:
    """Tests for RAGState TypedDict."""

    def test_initial_state(self, sample_state):
        """Test initial state structure."""
        assert sample_state["original_query"] == "Как работает авторизация?"
        assert sample_state["rewritten_query"] == ""
        assert sample_state["retrieved_docs"] == []
        assert sample_state["relevant_docs"] == []
        assert sample_state["answer"] == ""
        assert sample_state["has_relevant_docs"] is False
        assert sample_state["is_hallucinated"] is False
        assert sample_state["retry_count"] == 0
        assert sample_state["max_retries"] == 2
        assert sample_state["sources"] == []
        assert sample_state["error"] is None

    def test_state_with_documents(self, sample_state, sample_documents):
        """Test state with retrieved documents."""
        sample_state["retrieved_docs"] = sample_documents
        sample_state["relevant_docs"] = sample_documents[:2]
        sample_state["has_relevant_docs"] = True

        assert len(sample_state["retrieved_docs"]) == 3
        assert len(sample_state["relevant_docs"]) == 2
        assert sample_state["has_relevant_docs"] is True

    def test_state_after_generation(self, sample_state):
        """Test state after answer generation."""
        sample_state["answer"] = "JWT токены используются для авторизации."
        sample_state["sources"] = ["auth_flow.md"]

        assert "JWT" in sample_state["answer"]
        assert "auth_flow.md" in sample_state["sources"]
