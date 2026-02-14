"""
Tests for MCP server tools.
"""

import pytest
from unittest.mock import patch, MagicMock
import tempfile
import os


class TestIndexFolder:
    """Tests for index_folder tool."""

    def test_index_folder_nonexistent_path(self):
        """Test error handling for nonexistent folder."""
        with patch("server.get_vector_store") as mock_get_vs:
            from server import index_folder

            result = index_folder("/nonexistent/path")

            assert "Ошибка" in result
            assert "не существует" in result

    def test_index_folder_success(self, temp_docs_folder):
        """Test successful folder indexing."""
        mock_vs = MagicMock()
        mock_vs.index_folder.return_value = {
            "documents_loaded": 2,
            "chunks_indexed": 4,
            "collection_size": 4,
        }

        with patch("server.get_vector_store", return_value=mock_vs):
            from server import index_folder

            result = index_folder(temp_docs_folder, reset=True)

            assert "Индексация завершена" in result
            assert "2" in result  # documents_loaded
            mock_vs.index_folder.assert_called_once()


class TestAskQuestion:
    """Tests for ask_question tool."""

    def test_ask_question_success(self):
        """Test successful question answering."""
        mock_chain = MagicMock()

        with patch("server.get_chain", return_value=mock_chain):
            with patch("server.rag_ask") as mock_ask:
                mock_ask.return_value = {
                    "answer": "JWT используется для авторизации",
                    "sources": ["auth_flow.md"],
                    "error": None,
                }

                from server import ask_question

                result = ask_question("Как работает авторизация?")

                assert "JWT" in result
                assert "auth_flow.md" in result

    def test_ask_question_error(self):
        """Test error handling in question answering."""
        mock_chain = MagicMock()

        with patch("server.get_chain", return_value=mock_chain):
            with patch("server.rag_ask") as mock_ask:
                mock_ask.return_value = {
                    "answer": "",
                    "sources": [],
                    "error": "Connection failed",
                }

                from server import ask_question

                result = ask_question("Test question")

                assert "Ошибка" in result


class TestFindRelevantDocs:
    """Tests for find_relevant_docs tool."""

    def test_find_relevant_docs_success(self):
        """Test successful document search."""
        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            {
                "content": "JWT авторизация через токены",
                "source": "auth_flow.md",
                "distance": 0.1,
            },
        ]

        with patch("server.get_vector_store", return_value=mock_vs):
            from server import find_relevant_docs

            result = find_relevant_docs("авторизация", n_results=3)

            assert "auth_flow.md" in result
            assert "JWT" in result

    def test_find_relevant_docs_empty(self):
        """Test when no documents found."""
        mock_vs = MagicMock()
        mock_vs.search.return_value = []

        with patch("server.get_vector_store", return_value=mock_vs):
            from server import find_relevant_docs

            result = find_relevant_docs("несуществующий запрос")

            assert "не найдены" in result.lower()


class TestSummarizeDocument:
    """Tests for summarize_document tool."""

    def test_summarize_nonexistent_file(self):
        """Test error handling for nonexistent file."""
        from server import summarize_document

        result = summarize_document("/nonexistent/file.md")

        assert "Ошибка" in result
        assert "не существует" in result

    def test_summarize_success(self, temp_docs_folder):
        """Test successful document summarization."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Краткое содержание документа"

        with patch("server.get_llm", return_value=mock_llm):
            from server import summarize_document

            doc_path = os.path.join(temp_docs_folder, "test1.md")
            result = summarize_document(doc_path)

            assert "test1.md" in result
            assert "Краткое содержание" in result


class TestIndexStatus:
    """Tests for index_status tool."""

    def test_index_status_success(self):
        """Test successful status retrieval."""
        mock_vs = MagicMock()
        mock_vs.get_status.return_value = {
            "indexed": True,
            "total_chunks": 100,
            "collection_name": "documents",
            "chroma_path": "/app/chroma_db",
        }

        with patch("server.get_vector_store", return_value=mock_vs):
            from server import index_status

            result = index_status()

            assert "100" in result
            assert "documents" in result

    def test_index_status_not_indexed(self):
        """Test status when not indexed."""
        mock_vs = MagicMock()
        mock_vs.get_status.return_value = {
            "indexed": False,
            "error": "Collection not found",
        }

        with patch("server.get_vector_store", return_value=mock_vs):
            from server import index_status

            result = index_status()

            assert "не создан" in result.lower() or "ошибка" in result.lower()
