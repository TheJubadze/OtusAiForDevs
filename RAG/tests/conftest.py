"""
Pytest fixtures for RAG tests.
"""

import pytest
from unittest.mock import MagicMock, patch
import tempfile
import os

from rag.state import RAGState, Document


@pytest.fixture
def sample_state() -> RAGState:
    """Sample RAG state for testing."""
    return {
        "original_query": "Как работает авторизация?",
        "rewritten_query": "",
        "retrieved_docs": [],
        "relevant_docs": [],
        "answer": "",
        "has_relevant_docs": False,
        "is_hallucinated": False,
        "retry_count": 0,
        "max_retries": 2,
        "sources": [],
        "error": None,
    }


@pytest.fixture
def sample_documents() -> list[Document]:
    """Sample documents for testing."""
    return [
        Document(
            content="JWT токены используются для авторизации. Access token живёт 15 минут.",
            source="auth_flow.md",
            relevance_score=0.95,
        ),
        Document(
            content="Пользователи имеют роли: admin, manager, user.",
            source="auth_flow.md",
            relevance_score=0.85,
        ),
        Document(
            content="База данных PostgreSQL хранит данные пользователей.",
            source="database_schema.md",
            relevance_score=0.70,
        ),
    ]


@pytest.fixture
def mock_llm():
    """Mock LLM for testing."""
    mock = MagicMock()
    mock.generate.return_value = "Мок-ответ от LLM"
    mock.generate_json.return_value = '{"relevant": true}'
    return mock


@pytest.fixture
def mock_vector_store():
    """Mock VectorStore for testing."""
    mock = MagicMock()
    mock.search.return_value = [
        {
            "content": "JWT авторизация работает через токены.",
            "source": "auth_flow.md",
            "distance": 0.1,
        },
        {
            "content": "Access token обновляется через refresh token.",
            "source": "auth_flow.md",
            "distance": 0.2,
        },
    ]
    mock.get_status.return_value = {
        "indexed": True,
        "total_chunks": 100,
        "collection_name": "test_docs",
        "chroma_path": "/tmp/chroma",
    }
    mock.index_folder.return_value = {
        "documents_loaded": 10,
        "chunks_indexed": 50,
        "collection_size": 50,
    }
    return mock


@pytest.fixture
def temp_docs_folder():
    """Create temporary folder with test documents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test documents
        doc1 = os.path.join(tmpdir, "test1.md")
        with open(doc1, "w", encoding="utf-8") as f:
            f.write("# Тестовый документ 1\n\nСодержимое первого документа.")

        doc2 = os.path.join(tmpdir, "test2.md")
        with open(doc2, "w", encoding="utf-8") as f:
            f.write("# Тестовый документ 2\n\nСодержимое второго документа.")

        yield tmpdir
