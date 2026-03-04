"""
Tests for RAG graph nodes.
"""

import pytest
from unittest.mock import MagicMock, patch
import json

from rag.nodes import create_nodes
from rag.state import RAGState, Document


class TestRewriteQueryNode:
    """Tests for rewrite_query node."""

    def test_rewrite_query_first_pass(self, sample_state, mock_vector_store, mock_llm):
        """Test query rewriting on first pass."""
        mock_llm.generate.return_value = "Переписанный запрос"

        nodes = create_nodes(mock_vector_store, mock_llm)
        result = nodes["rewrite_query"](sample_state)

        assert "rewritten_query" in result
        assert result["rewritten_query"] == "Переписанный запрос"
        mock_llm.generate.assert_called_once()

    def test_rewrite_query_retry(self, sample_state, mock_vector_store, mock_llm):
        """Test query rewriting on retry."""
        sample_state["retry_count"] = 1
        sample_state["rewritten_query"] = "Предыдущий запрос"
        mock_llm.generate.return_value = "Новый запрос"

        nodes = create_nodes(mock_vector_store, mock_llm)
        result = nodes["rewrite_query"](sample_state)

        assert result["rewritten_query"] == "Новый запрос"
        # Check that prompt mentions previous attempt
        call_args = mock_llm.generate.call_args[0][0]
        assert "Предыдущий запрос" in call_args or "Предыдущая попытка" in call_args


class TestRetrieveNode:
    """Tests for retrieve node."""

    def test_retrieve_returns_documents(self, sample_state, mock_vector_store, mock_llm):
        """Test that retrieve returns documents."""
        sample_state["rewritten_query"] = "авторизация"

        nodes = create_nodes(mock_vector_store, mock_llm)
        result = nodes["retrieve"](sample_state)

        assert "retrieved_docs" in result
        assert len(result["retrieved_docs"]) == 2
        mock_vector_store.search.assert_called_once()

    def test_retrieve_uses_original_query_if_no_rewritten(
        self, sample_state, mock_vector_store, mock_llm
    ):
        """Test that retrieve uses original query when rewritten is empty."""
        sample_state["rewritten_query"] = ""

        nodes = create_nodes(mock_vector_store, mock_llm)
        nodes["retrieve"](sample_state)

        mock_vector_store.search.assert_called_with(
            sample_state["original_query"], n_results=5
        )


class TestGradeChunksNode:
    """Tests for grade_chunks node."""

    def test_grade_chunks_filters_relevant(
        self, sample_state, sample_documents, mock_vector_store, mock_llm
    ):
        """Test that grade_chunks filters relevant documents."""
        sample_state["retrieved_docs"] = sample_documents
        mock_llm.generate_json.return_value = '{"relevant": true}'

        nodes = create_nodes(mock_vector_store, mock_llm)
        result = nodes["grade_chunks"](sample_state)

        assert "relevant_docs" in result
        assert "has_relevant_docs" in result
        assert result["has_relevant_docs"] is True
        assert len(result["relevant_docs"]) == len(sample_documents)

    def test_grade_chunks_handles_irrelevant(
        self, sample_state, sample_documents, mock_vector_store, mock_llm
    ):
        """Test handling of irrelevant documents."""
        sample_state["retrieved_docs"] = sample_documents
        mock_llm.generate_json.return_value = '{"relevant": false}'

        nodes = create_nodes(mock_vector_store, mock_llm)
        result = nodes["grade_chunks"](sample_state)

        assert result["has_relevant_docs"] is False
        assert len(result["relevant_docs"]) == 0


class TestGenerateNode:
    """Tests for generate node."""

    def test_generate_with_docs(
        self, sample_state, sample_documents, mock_vector_store, mock_llm
    ):
        """Test answer generation with documents."""
        sample_state["relevant_docs"] = sample_documents
        mock_llm.generate.return_value = "JWT используется для авторизации."

        nodes = create_nodes(mock_vector_store, mock_llm)
        result = nodes["generate"](sample_state)

        assert "answer" in result
        assert "sources" in result
        assert "JWT" in result["answer"]
        assert len(result["sources"]) > 0

    def test_generate_without_docs(self, sample_state, mock_vector_store, mock_llm):
        """Test answer generation without documents."""
        sample_state["relevant_docs"] = []

        nodes = create_nodes(mock_vector_store, mock_llm)
        result = nodes["generate"](sample_state)

        assert "не найдена" in result["answer"].lower()
        assert result["sources"] == []


class TestHallucinationCheckNode:
    """Tests for hallucination_check node."""

    def test_hallucination_check_grounded(
        self, sample_state, sample_documents, mock_vector_store, mock_llm
    ):
        """Test hallucination check for grounded answer."""
        sample_state["answer"] = "JWT токены используются для авторизации."
        sample_state["relevant_docs"] = sample_documents
        mock_llm.generate_json.return_value = '{"grounded": true}'

        nodes = create_nodes(mock_vector_store, mock_llm)
        result = nodes["hallucination_check"](sample_state)

        assert result["is_hallucinated"] is False

    def test_hallucination_check_hallucinated(
        self, sample_state, sample_documents, mock_vector_store, mock_llm
    ):
        """Test hallucination check for hallucinated answer."""
        sample_state["answer"] = "Используется OAuth2 с Google."
        sample_state["relevant_docs"] = sample_documents
        mock_llm.generate_json.return_value = '{"grounded": false}'

        nodes = create_nodes(mock_vector_store, mock_llm)
        result = nodes["hallucination_check"](sample_state)

        assert result["is_hallucinated"] is True


class TestPrepareRetryNode:
    """Tests for prepare_retry node."""

    def test_prepare_retry_increments_counter(
        self, sample_state, mock_vector_store, mock_llm
    ):
        """Test that prepare_retry increments retry counter."""
        sample_state["retry_count"] = 0

        nodes = create_nodes(mock_vector_store, mock_llm)
        result = nodes["prepare_retry"](sample_state)

        assert result["retry_count"] == 1
        assert result["retrieved_docs"] == []
        assert result["relevant_docs"] == []
        assert result["answer"] == ""
