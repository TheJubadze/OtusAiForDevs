"""
Corrective RAG: State definition.
"""

from typing import TypedDict, List, Optional


class Document(TypedDict):
    """Retrieved document chunk."""
    content: str
    source: str
    relevance_score: Optional[float]


class RAGState(TypedDict):
    """State for the Corrective RAG graph."""

    # Input
    original_query: str

    # Query processing
    rewritten_query: str

    # Retrieval
    retrieved_docs: List[Document]
    relevant_docs: List[Document]

    # Generation
    answer: str

    # Checks
    has_relevant_docs: bool
    is_hallucinated: bool

    # Control flow
    retry_count: int
    max_retries: int

    # Final output
    sources: List[str]
    error: Optional[str]
