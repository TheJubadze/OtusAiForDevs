"""
Tests for RAG graph assembly and routing.
"""

import pytest
from unittest.mock import MagicMock, patch

from rag.graph import (
    build_graph,
    route_after_grading,
    route_after_hallucination_check,
)
from rag.state import RAGState


class TestRoutingFunctions:
    """Tests for graph routing functions."""

    def test_route_after_grading_has_relevant(self, sample_state):
        """Test routing when relevant docs found."""
        sample_state["has_relevant_docs"] = True

        result = route_after_grading(sample_state)

        assert result == "generate"

    def test_route_after_grading_no_relevant_can_retry(self, sample_state):
        """Test routing when no relevant docs but can retry."""
        sample_state["has_relevant_docs"] = False
        sample_state["retry_count"] = 0
        sample_state["max_retries"] = 2

        result = route_after_grading(sample_state)

        assert result == "prepare_retry"

    def test_route_after_grading_no_relevant_max_retries(self, sample_state):
        """Test routing when no relevant docs and max retries reached."""
        sample_state["has_relevant_docs"] = False
        sample_state["retry_count"] = 2
        sample_state["max_retries"] = 2

        result = route_after_grading(sample_state)

        assert result == "finalize"

    def test_route_after_hallucination_not_hallucinated(self, sample_state):
        """Test routing when answer is grounded."""
        sample_state["is_hallucinated"] = False

        result = route_after_hallucination_check(sample_state)

        assert result == "finalize"

    def test_route_after_hallucination_can_retry(self, sample_state):
        """Test routing when hallucinated but can retry."""
        sample_state["is_hallucinated"] = True
        sample_state["retry_count"] = 0
        sample_state["max_retries"] = 2

        result = route_after_hallucination_check(sample_state)

        assert result == "prepare_retry"

    def test_route_after_hallucination_max_retries(self, sample_state):
        """Test routing when hallucinated and max retries reached."""
        sample_state["is_hallucinated"] = True
        sample_state["retry_count"] = 2
        sample_state["max_retries"] = 2

        result = route_after_hallucination_check(sample_state)

        assert result == "finalize"


class TestBuildGraph:
    """Tests for graph building."""

    def test_build_graph_returns_stategraph(self, mock_vector_store, mock_llm):
        """Test that build_graph returns a StateGraph."""
        from langgraph.graph import StateGraph

        graph = build_graph(mock_vector_store, mock_llm)

        assert isinstance(graph, StateGraph)

    def test_build_graph_has_all_nodes(self, mock_vector_store, mock_llm):
        """Test that graph has all required nodes."""
        graph = build_graph(mock_vector_store, mock_llm)

        expected_nodes = [
            "rewrite_query",
            "retrieve",
            "grade_chunks",
            "generate",
            "hallucination_check",
            "prepare_retry",
            "finalize",
        ]

        for node in expected_nodes:
            assert node in graph.nodes, f"Missing node: {node}"

    def test_graph_compiles(self, mock_vector_store, mock_llm):
        """Test that graph compiles without errors."""
        graph = build_graph(mock_vector_store, mock_llm)

        compiled = graph.compile()

        assert compiled is not None
