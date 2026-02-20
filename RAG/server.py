"""
RAG Knowledge Base MCP Server.

Инструменты:
- index_folder: Индексация папки с документами
- ask_question: Полный RAG-пайплайн (поиск + генерация)
- find_relevant_docs: Поиск релевантных документов без генерации
- summarize_document: Суммаризация документа
- index_status: Статус индекса
"""

from fastmcp import FastMCP
from typing import Optional
import os

from rag import create_rag_chain, ask_question as rag_ask, VectorStore, LLM
from rag.graph import build_graph


# Initialize MCP server
mcp = FastMCP(
    name="rag-knowledge-base",
    instructions="RAG Knowledge Base с локальной LLM. Индексирует документы и отвечает на вопросы.",
)


class AppState:
    """Lazy-initialized application state container."""

    def __init__(self):
        self._vector_store: Optional[VectorStore] = None
        self._llm: Optional[LLM] = None
        self._chain = None

    @property
    def vector_store(self) -> VectorStore:
        if self._vector_store is None:
            self._vector_store = VectorStore(
                chroma_path=os.environ.get("CHROMA_PATH", "./chroma_db"),
                collection_name=os.environ.get("COLLECTION_NAME", "documents"),
            )
        return self._vector_store

    @property
    def llm(self) -> LLM:
        if self._llm is None:
            self._llm = LLM(model=os.environ.get("LLM_MODEL", "qwen2.5:3b"))
        return self._llm

    @property
    def chain(self):
        if self._chain is None:
            graph = build_graph(self.vector_store, self.llm)
            self._chain = graph.compile()
        return self._chain


app_state = AppState()


def get_vector_store() -> VectorStore:
    """Get VectorStore instance."""
    return app_state.vector_store


def get_llm() -> LLM:
    """Get LLM instance."""
    return app_state.llm


def get_chain():
    """Get compiled RAG chain."""
    return app_state.chain


@mcp.tool()
def index_folder(
    folder_path: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
    reset: bool = False,
) -> str:
    """
    Индексирует папку с документами в векторную базу данных.

    Args:
        folder_path: Путь к папке с документами
        chunk_size: Размер чанка в символах (default: 1000)
        chunk_overlap: Перекрытие между чанками (default: 100)
        reset: Пересоздать индекс с нуля (default: False)

    Returns:
        Статистика индексации
    """
    if not os.path.isdir(folder_path):
        return f"Ошибка: папка '{folder_path}' не существует"

    try:
        vs = get_vector_store()
        result = vs.index_folder(
            folder_path=folder_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            reset=reset,
        )

        return (
            f"Индексация завершена:\n"
            f"- Загружено документов: {result['documents_loaded']}\n"
            f"- Создано чанков: {result['chunks_indexed']}\n"
            f"- Всего в индексе: {result['collection_size']}"
        )
    except Exception as e:
        return f"Ошибка индексации: {str(e)}"


@mcp.tool()
def ask_question(question: str, max_retries: int = 2) -> str:
    """
    Задаёт вопрос по индексированным документам (полный RAG-пайплайн).

    Использует Corrective RAG: переписывание запроса, оценка релевантности,
    проверка на галлюцинации, повторные попытки при необходимости.

    Args:
        question: Вопрос на естественном языке
        max_retries: Максимум повторных попыток (default: 2)

    Returns:
        Ответ на вопрос с указанием источников
    """
    try:
        chain = get_chain()
        result = rag_ask(
            question=question,
            chain=chain,
            max_retries=max_retries,
        )

        if result.get("error"):
            return f"Ошибка: {result['error']}"

        answer = result.get("answer", "Не удалось получить ответ")
        sources = result.get("sources", [])

        if sources:
            return f"{answer}\n\n📎 Источники: {', '.join(sources)}"
        return answer

    except Exception as e:
        return f"Ошибка: {str(e)}"


@mcp.tool()
def find_relevant_docs(query: str, n_results: int = 5) -> str:
    """
    Ищет релевантные документы без генерации ответа.

    Полезно для просмотра, какие документы будут использованы для ответа.

    Args:
        query: Поисковый запрос
        n_results: Количество результатов (default: 5)

    Returns:
        Список найденных документов с превью содержимого
    """
    try:
        vs = get_vector_store()
        results = vs.search(query, n_results=n_results)

        if not results:
            return "Документы не найдены"

        output = []
        for i, doc in enumerate(results, 1):
            source = doc["source"].split("\\")[-1].split("/")[-1]
            preview = doc["content"][:200].replace("\n", " ")
            distance = doc.get("distance")
            score = f" (score: {1-distance:.2f})" if distance else ""

            output.append(f"{i}. **{source}**{score}\n   {preview}...")

        return "\n\n".join(output)

    except Exception as e:
        return f"Ошибка поиска: {str(e)}"


@mcp.tool()
def summarize_document(file_path: str) -> str:
    """
    Создаёт краткое содержание документа.

    Args:
        file_path: Путь к файлу документа

    Returns:
        Краткое содержание документа
    """
    if not os.path.isfile(file_path):
        return f"Ошибка: файл '{file_path}' не существует"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if len(content) > 10000:
            content = content[:10000] + "\n\n[...документ обрезан...]"

        llm = get_llm()
        prompt = f"""Создай краткое содержание документа на русском языке.
Выдели основные темы и ключевые моменты.
Формат: 3-5 пунктов.

ДОКУМЕНТ:
{content}

КРАТКОЕ СОДЕРЖАНИЕ:"""

        summary = llm.generate(prompt, temperature=0.3)

        filename = os.path.basename(file_path)
        return f"📄 **{filename}**\n\n{summary}"

    except Exception as e:
        return f"Ошибка: {str(e)}"


@mcp.tool()
def index_status() -> str:
    """
    Показывает статус индекса: количество документов, путь к базе и т.д.

    Returns:
        Информация о текущем состоянии индекса
    """
    try:
        vs = get_vector_store()
        status = vs.get_status()

        if not status.get("indexed"):
            return f"Индекс не создан или пуст\nОшибка: {status.get('error', 'неизвестно')}"

        return (
            f"📊 Статус индекса:\n"
            f"- Коллекция: {status['collection_name']}\n"
            f"- Чанков в индексе: {status['total_chunks']}\n"
            f"- Путь к базе: {status['chroma_path']}"
        )

    except Exception as e:
        return f"Ошибка: {str(e)}"


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.run(transport="sse", host="0.0.0.0", port=8000)
    else:
        mcp.run()
