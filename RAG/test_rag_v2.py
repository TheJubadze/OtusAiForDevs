"""
RAG v2: используем Ollama для эмбеддингов (nomic-embed-text).
Качество поиска по русскоязычным документам значительно лучше.
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
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n## ", "\n### ", "\n\n", "\n", " "],
)
chunks = splitter.split_documents(documents)
print(f"   Получилось чанков: {len(chunks)}")

# Используем Ollama для эмбеддингов
ollama_ef = ef.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text",
)

print("💾 Индексируем через nomic-embed-text...")
client = chromadb.PersistentClient(path="./chroma_db_v2")

try:
    client.delete_collection("taskflow_docs_v2")
except:
    pass

collection = client.create_collection(
    name="taskflow_docs_v2",
    embedding_function=ollama_ef,
    metadata={"hnsw:space": "cosine"},
)

# Добавляем пачками по 20 (Ollama обрабатывает не мгновенно)
batch_size = 20
for i in range(0, len(chunks), batch_size):
    batch = chunks[i : i + batch_size]
    collection.add(
        ids=[f"chunk_{i+j}" for j in range(len(batch))],
        documents=[c.page_content for c in batch],
        metadatas=[{"source": c.metadata.get("source", "unknown")} for c in batch],
    )
    print(f"   ... {min(i + batch_size, len(chunks))}/{len(chunks)}")

print(f"✅ Индекс создан: {collection.count()} чанков\n")


# --- ПОИСК + ГЕНЕРАЦИЯ ---

def ask(question: str) -> str:
    results = collection.query(query_texts=[question], n_results=5)
    documents = results["documents"][0]
    sources = results["metadatas"][0]

    context = ""
    source_files = set()
    for doc, meta in zip(documents, sources):
        context += doc + "\n\n---\n\n"
        source_files.add(meta["source"].split("\\")[-1])

    prompt = f"""Ты — помощник разработчика проекта TaskFlow. 
Отвечай ТОЛЬКО на основе предоставленного контекста. 
Если в контексте нет информации — честно скажи об этом.
Отвечай на русском, кратко и структурированно.

КОНТЕКСТ:
{context}

ВОПРОС: {question}

ОТВЕТ:"""

    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[{"role": "user", "content": prompt}],
    )

    answer = response["message"]["content"]
    return f"{answer}\n\n📎 Источники: {', '.join(source_files)}"


# Тестируем те же вопросы
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