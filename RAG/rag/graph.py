"""
Corrective RAG: LangGraph graph definition.

Graph structure:
    START → rewrite_query → retrieve → grade_chunks → [conditional]

    After grade_chunks:
        - has_relevant_docs=True → generate → hallucination_check → [conditional]
        - has_relevant_docs=False → [check_retry]

    After hallucination_check:
        - is_hallucinated=False → finalize → END
        - is_hallucinated=True → [check_retry]

    check_retry:
        - retry_count < max_retries → prepare_retry → rewrite_query (loop)
        - retry_count >= max_retries → finalize → END
"""

from langgraph.graph import StateGraph, START, END
from typing import Optional, Literal

from .state import RAGState
from .nodes import create_nodes
from .utils import VectorStore, LLM


def route_after_grading(state: RAGState) -> Literal["generate", "prepare_retry", "finalize"]:
    """Route after grading: generate if relevant docs, otherwise check retry."""
    if state.get("has_relevant_docs", False):
        return "generate"

    # No relevant docs - check if we can retry
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if retry_count < max_retries:
        return "prepare_retry"
    return "finalize"


def route_after_hallucination_check(state: RAGState) -> Literal["prepare_retry", "finalize"]:
    """Route after hallucination check: retry if hallucinated, otherwise finalize."""
    if not state.get("is_hallucinated", False):
        return "finalize"

    # Hallucinated - check if we can retry
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if retry_count < max_retries:
        return "prepare_retry"
    return "finalize"


def build_graph(
    vector_store: Optional[VectorStore] = None,
    llm: Optional[LLM] = None,
) -> StateGraph:
    """Build the Corrective RAG graph."""

    # Use defaults if not provided
    if vector_store is None:
        vector_store = VectorStore()
    if llm is None:
        llm = LLM()

    # Create nodes
    nodes = create_nodes(vector_store, llm)

    # Build graph
    graph = StateGraph(RAGState)

    # Add nodes
    graph.add_node("rewrite_query", nodes["rewrite_query"])
    graph.add_node("retrieve", nodes["retrieve"])
    graph.add_node("grade_chunks", nodes["grade_chunks"])
    graph.add_node("generate", nodes["generate"])
    graph.add_node("hallucination_check", nodes["hallucination_check"])
    graph.add_node("prepare_retry", nodes["prepare_retry"])
    graph.add_node("finalize", nodes["finalize"])

    # Linear edges
    graph.add_edge(START, "rewrite_query")
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("retrieve", "grade_chunks")
    graph.add_edge("generate", "hallucination_check")
    graph.add_edge("prepare_retry", "rewrite_query")
    graph.add_edge("finalize", END)

    # Conditional: after grading chunks
    graph.add_conditional_edges(
        "grade_chunks",
        route_after_grading,
        {
            "generate": "generate",
            "prepare_retry": "prepare_retry",
            "finalize": "finalize",
        },
    )

    # Conditional: after hallucination check
    graph.add_conditional_edges(
        "hallucination_check",
        route_after_hallucination_check,
        {
            "prepare_retry": "prepare_retry",
            "finalize": "finalize",
        },
    )

    return graph


def create_rag_chain(
    chroma_path: str = "./chroma_db",
    collection_name: str = "documents",
    llm_model: str = "qwen2.5:3b",
):
    """Create a compiled RAG chain ready for invocation."""

    vector_store = VectorStore(
        chroma_path=chroma_path,
        collection_name=collection_name,
    )

    llm = LLM(model=llm_model)

    graph = build_graph(vector_store, llm)

    return graph.compile(), vector_store, llm


def ask_question(
    question: str,
    chain=None,
    vector_store: Optional[VectorStore] = None,
    llm: Optional[LLM] = None,
    max_retries: int = 2,
) -> dict:
    """
    Ask a question using the Corrective RAG chain.

    Returns:
        dict with keys: answer, sources, error
    """

    if chain is None:
        graph = build_graph(vector_store, llm)
        chain = graph.compile()

    initial_state: RAGState = {
        "original_query": question,
        "rewritten_query": "",
        "retrieved_docs": [],
        "relevant_docs": [],
        "answer": "",
        "has_relevant_docs": False,
        "is_hallucinated": False,
        "retry_count": 0,
        "max_retries": max_retries,
        "sources": [],
        "error": None,
    }

    try:
        final_state = chain.invoke(initial_state)

        return {
            "answer": final_state.get("answer", ""),
            "sources": final_state.get("sources", []),
            "error": final_state.get("error"),
        }
    except Exception as e:
        return {
            "answer": "",
            "sources": [],
            "error": str(e),
        }
