"""
Tests for RAG utilities (VectorStore, LLM).
"""

import pytest
from unittest.mock import patch, MagicMock
import tempfile
import os


class TestVectorStore:
    """Tests for VectorStore class."""

    def test_get_status_empty(self):
        """Test status when collection doesn't exist."""
        tmpdir = tempfile.mkdtemp()
        try:
            from rag.utils import VectorStore

            vs = VectorStore(
                chroma_path=tmpdir,
                collection_name="nonexistent",
            )

            status = vs.get_status()
            # New collection will be created with 0 items
            assert status["indexed"] is True
            assert status["total_chunks"] == 0
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_search_returns_list(self, mock_vector_store):
        """Test that search returns a list of documents."""
        results = mock_vector_store.search("test query", n_results=5)

        assert isinstance(results, list)
        assert len(results) == 2
        assert "content" in results[0]
        assert "source" in results[0]

    def test_index_folder_returns_stats(self, mock_vector_store):
        """Test that index_folder returns statistics."""
        result = mock_vector_store.index_folder("/tmp/docs", reset=True)

        assert "documents_loaded" in result
        assert "chunks_indexed" in result
        assert "collection_size" in result
        assert result["documents_loaded"] == 10

    def test_get_status_returns_info(self, mock_vector_store):
        """Test that get_status returns index info."""
        status = mock_vector_store.get_status()

        assert status["indexed"] is True
        assert status["total_chunks"] == 100
        assert status["collection_name"] == "test_docs"


class TestLLM:
    """Tests for LLM class."""

    def test_generate_returns_string(self, mock_llm):
        """Test that generate returns a string."""
        result = mock_llm.generate("Test prompt")

        assert isinstance(result, str)
        assert result == "Мок-ответ от LLM"

    def test_generate_json_returns_json(self, mock_llm):
        """Test that generate_json returns JSON string."""
        result = mock_llm.generate_json("Return JSON")

        assert isinstance(result, str)
        assert "relevant" in result

    @patch("rag.utils.ollama.Client")
    def test_llm_uses_custom_host(self, mock_client_class):
        """Test that LLM uses custom Ollama host."""
        from rag.utils import LLM

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        llm = LLM(model="test-model", host="http://custom:11434")

        mock_client_class.assert_called_with(host="http://custom:11434")
