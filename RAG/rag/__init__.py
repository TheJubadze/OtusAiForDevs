"""
Corrective RAG module.

Usage:
    from rag import create_rag_chain, ask_question, VectorStore

    # Create chain
    chain, vector_store, llm = create_rag_chain()

    # Index documents
    vector_store.index_folder("./sample_docs", reset=True)

    # Ask question
    result = ask_question("How does authentication work?", chain=chain)
    print(result["answer"])
"""

from .state import RAGState, Document
from .utils import VectorStore, LLM
from .nodes import create_nodes
from .graph import build_graph, create_rag_chain, ask_question

__all__ = [
    "RAGState",
    "Document",
    "VectorStore",
    "LLM",
    "create_nodes",
    "build_graph",
    "create_rag_chain",
    "ask_question",
]
