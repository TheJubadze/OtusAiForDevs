"""
RAG v3: увеличенные чанки + улучшенный промпт.
"""

import chromadb
import chromadb.utils.embedding_functions as ef
import ollama
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


# --- ИНДЕКСАЦИЯ ---

print("📂 Загружаем документы...")
loader = DirectoryLoader(
    "./sample_docs",
    glob="**/*.*",
    loader_cls=TextLoader,
    loader_kwargs={"encoding": "utf-8"},
)
documents = loader.load()
print(f"   Загружено файлов: {len(documents)}")

print("✂️  Разбиваем на чанки...")
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,       # увеличили с 500
    chunk_overlap=100,     # увеличили с 50
    separators=["\n## ", "\n### ", "\n\n", "\n", " "],
)
chunks = splitter.split_documents(documents)
print(f"   Получилось чанков: {len(chunks)}")

ollama_ef = ef.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text",
)

print("💾 Индексируем...")
client = chromadb.PersistentClient(path="./chroma_db_v3")
try:
    client.delete_collection("taskflow_v3")
except:
    pass

collection = client.create_collection(
    name="taskflow_v3",
    embedding_function=ollama_ef,
    metadata={"hnsw:space": "cosine"},
)

batch_size = 20
for i in range(0, len(chunks), batch_size):
    batch = chunks[i : i + batch_size]
    collection.add(
        ids=[f"chunk_{i+j}" for j in range(len(batch))],
        documents=[c.page_content for c in batch],
        metadatas=[{"source": c.metadata.get("source", "unknown")} for c in batch],
    )
    print(f"   ... {min(i + batch_size, len(chunks))}/{len(chunks)}")

print(f"✅ Индекс: {collection.count()} чанков\n")


# --- RAG ---

def ask(question: str) -> str:
    results = collection.query(query_texts=[question], n_results=5)

    # Показываем что нашли (для отладки)
    print(f"   🔍 Найденные источники:")
    source_files = set()
    for meta in results["metadatas"][0]:
        src = meta["source"].split("\\")[-1]
        source_files.add(src)
        print(f"      - {src}")

    context = "\n\n---\n\n".join(results["documents"][0])

    prompt = f"""Ты — ассистент по документации проекта TaskFlow.

СТРОГИЕ ПРАВИЛА:
1. Отвечай ТОЛЬКО на основе контекста ниже
2. Если в контексте НЕТ информации для ответа — скажи: "В документации не найдена информация по этому вопросу"
3. НЕ ВЫДУМЫВАЙ информацию, которой нет в контексте
4. Цитируй конкретные детали из контекста
5. Отвечай на русском, кратко

КОНТЕКСТ:
{context}

ВОПРОС: {question}

ОТВЕТ:"""

    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[{"role": "user", "content": prompt}],
    )

    return f"{response['message']['content']}\n\n📎 Источники: {', '.join(source_files)}"


questions = [
    "Как работает авторизация в системе?",
    "Что делать, если RabbitMQ не принимает сообщения?",
    "Какие роли пользователей есть и что они могут делать?",
    "Как запустить тесты?",
    "Какой пароль у тестового пользователя admin?",
]

for q in questions:
    print(f"\n❓ {q}")
    answer = ask(q)
    print(f"💬 {answer}")
    print("=" * 80)