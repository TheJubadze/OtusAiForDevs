"""
Полный RAG: поиск по документам + генерация ответа через Ollama.
"""

import chromadb
import ollama


# 1. Подключаемся к уже созданному индексу
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("taskflow_docs")
print(f"📚 Загружена коллекция: {collection.count()} чанков\n")


def ask(question: str) -> str:
    """Задать вопрос по документации."""

    # Шаг 1: Ищем релевантные чанки
    results = collection.query(query_texts=[question], n_results=5)
    documents = results["documents"][0]
    sources = results["metadatas"][0]

    # Собираем контекст
    context = ""
    source_files = set()
    for doc, meta in zip(documents, sources):
        context += doc + "\n\n---\n\n"
        source_files.add(meta["source"].split("\\")[-1])

    # Шаг 2: Формируем промпт для LLM
    prompt = f"""Ты — помощник разработчика. Отвечай на вопросы ТОЛЬКО на основе 
предоставленного контекста. Если в контексте нет ответа — скажи об этом.
Отвечай на русском языке, кратко и по делу.

КОНТЕКСТ:
{context}

ВОПРОС: {question}

ОТВЕТ:"""

    # Шаг 3: Генерируем ответ через Ollama
    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[{"role": "user", "content": prompt}],
    )

    answer = response["message"]["content"]
    return f"{answer}\n\n📎 Источники: {', '.join(source_files)}"


# Тестируем!
questions = [
    "Как работает авторизация в системе?",
    "Что делать, если RabbitMQ не принимает сообщения?",
    "Какие роли пользователей есть и что они могут делать?",
    "Как запустить тесты?",
]

for q in questions:
    print(f"❓ {q}")
    print(f"💬 {ask(q)}")
    print("=" * 80)