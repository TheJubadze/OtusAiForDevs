"""
Интерактивный чат через Corrective RAG + Ollama LLM.

Все настройки берутся из .env:
    CHROMA_PATH      — путь к индексу ChromaDB
    COLLECTION_NAME  — имя коллекции
    LLM_MODEL        — модель Ollama (по умолчанию qwen2.5:3b)

Запуск:
    python chat.py
"""

import io
import sys
import os

# UTF-8 для Windows-консоли
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from rag.graph import create_rag_chain, ask_question

CHROMA_PATH = os.environ.get("CHROMA_PATH", "./chroma_db")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "documents")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2.5:3b")


def main():
    print("Загрузка RAG-пайплайна...")
    print(f"  Индекс:    {CHROMA_PATH}")
    print(f"  Коллекция: {COLLECTION_NAME}")
    print(f"  LLM:       {LLM_MODEL}")

    chain, vector_store, llm = create_rag_chain(
        chroma_path=CHROMA_PATH,
        collection_name=COLLECTION_NAME,
        llm_model=LLM_MODEL,
    )

    status = vector_store.get_status()
    chunks = status.get("total_chunks", 0)
    if chunks == 0:
        print("\n  Индекс пуст! Сначала проиндексируйте документы:")
        print("    python index_my_project.py")
        return

    print(f"  Чанков:    {chunks}")
    print()
    print("Задавайте вопросы. Для выхода: quit / exit / выход")
    print("-" * 60)

    while True:
        try:
            question = input("\nВопрос: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q", "выход"):
            print("До свидания!")
            break

        result = ask_question(question, chain=chain)

        if result.get("error"):
            print(f"Ошибка: {result['error']}")
            continue

        print(f"\nОтвет: {result['answer']}")
        if result.get("sources"):
            print(f"Источники: {', '.join(result['sources'])}")


if __name__ == "__main__":
    main()
