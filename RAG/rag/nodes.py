"""
Corrective RAG: Graph nodes.

Flow: rewrite_query → retrieve → grade_chunks → generate → hallucination_check
"""

import json
from typing import Dict, Any

from .state import RAGState, Document
from .utils import VectorStore, LLM


def create_nodes(vector_store: VectorStore, llm: LLM):
    """Factory function to create nodes with injected dependencies."""

    def rewrite_query(state: RAGState) -> Dict[str, Any]:
        """Rewrite the query for better retrieval."""

        original = state["original_query"]
        retry_count = state.get("retry_count", 0)

        # On first pass, use the original query as-is.
        # Small LLMs (3b) often corrupt specialized queries on rewrite.
        if retry_count == 0:
            return {"rewritten_query": original}
        else:
            # On retry, try different angle
            previous = state.get("rewritten_query", original)
            prompt = f"""Предыдущий поисковый запрос не дал релевантных результатов.
Переформулируй его, используя синонимы и альтернативные термины.

Исходный запрос: {original}
Предыдущая попытка: {previous}

Отвечай ТОЛЬКО новым запросом, без пояснений."""

        rewritten = llm.generate(prompt, temperature=0.3).strip()

        return {
            "rewritten_query": rewritten,
        }


    def retrieve(state: RAGState) -> Dict[str, Any]:
        """Retrieve documents from vector store using hybrid search."""

        query = state.get("rewritten_query") or state["original_query"]

        results = vector_store.hybrid_search(query, n_results=10)

        docs = [
            Document(
                content=r["content"],
                source=r["source"],
                relevance_score=1 - r["distance"] if r["distance"] else r.get("score"),
            )
            for r in results
        ]

        return {
            "retrieved_docs": docs,
        }


    def grade_chunks(state: RAGState) -> Dict[str, Any]:
        """Grade retrieved chunks for relevance.

        Small LLMs (3b) are unreliable at grading specialized/fictional content,
        so we pass all retrieved docs through and let generate decide.
        """

        docs = state["retrieved_docs"]

        return {
            "relevant_docs": docs,
            "has_relevant_docs": len(docs) > 0,
        }


    def generate(state: RAGState) -> Dict[str, Any]:
        """Generate answer from relevant documents."""

        query = state["original_query"]
        docs = state.get("relevant_docs", [])

        if not docs:
            return {
                "answer": "В документации не найдена информация по этому вопросу.",
                "sources": [],
            }

        context = "\n\n---\n\n".join([d["content"] for d in docs])
        sources = list(set([d["source"].split("\\")[-1].split("/")[-1] for d in docs]))

        prompt = f"""Ты — ассистент по документации проекта.

СТРОГИЕ ПРАВИЛА:
1. Отвечай ТОЛЬКО на основе контекста ниже
2. Если в контексте НЕТ информации для ответа — скажи: "В документации не найдена информация по этому вопросу"
3. НЕ ВЫДУМЫВАЙ информацию, которой нет в контексте
4. Цитируй конкретные детали из контекста
5. Отвечай на русском, кратко и по существу

КОНТЕКСТ:
{context}

ВОПРОС: {query}

ОТВЕТ:"""

        answer = llm.generate(prompt, temperature=0.1)

        return {
            "answer": answer,
            "sources": sources,
        }


    def hallucination_check(state: RAGState) -> Dict[str, Any]:
        """Check if the answer is grounded in the documents."""

        answer = state["answer"]
        docs = state.get("relevant_docs", [])

        # Skip check if no answer or no docs
        if not answer or not docs or "не найдена информация" in answer.lower():
            return {"is_hallucinated": False}

        context = "\n\n".join([d["content"] for d in docs])

        prompt = f"""Проверь, основан ли ответ на предоставленном контексте.

КОНТЕКСТ:
{context[:2000]}

ОТВЕТ:
{answer}

Ответ содержит ТОЛЬКО информацию из контекста (без выдумок)?
Отвечай JSON: {{"grounded": true}} или {{"grounded": false}}"""

        try:
            result = llm.generate_json(prompt)
            data = json.loads(result)
            is_hallucinated = not data.get("grounded", True)
        except (json.JSONDecodeError, KeyError):
            is_hallucinated = False

        return {
            "is_hallucinated": is_hallucinated,
        }


    def prepare_retry(state: RAGState) -> Dict[str, Any]:
        """Prepare state for retry."""
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "retrieved_docs": [],
            "relevant_docs": [],
            "answer": "",
        }


    def finalize(state: RAGState) -> Dict[str, Any]:
        """Finalize the response."""
        return {
            "error": None,
        }


    return {
        "rewrite_query": rewrite_query,
        "retrieve": retrieve,
        "grade_chunks": grade_chunks,
        "generate": generate,
        "hallucination_check": hallucination_check,
        "prepare_retry": prepare_retry,
        "finalize": finalize,
    }
