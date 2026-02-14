"""
Простой скрипт: загружаем документы из sample_docs в ChromaDB
и проверяем, что поиск работает.
"""

import chromadb
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


# 1. Загружаем все файлы из sample_docs
print("📂 Загружаем документы...")
loader = DirectoryLoader(
    "./sample_docs",
    glob="**/*.*",
    loader_cls=TextLoader,
    loader_kwargs={"encoding": "utf-8"},
)
documents = loader.load()
print(f"   Загружено файлов: {len(documents)}")

# 2. Разбиваем на чанки
print("✂️  Разбиваем на чанки...")
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n## ", "\n### ", "\n\n", "\n", " "],
)
chunks = splitter.split_documents(documents)
print(f"   Получилось чанков: {len(chunks)}")

# 3. Сохраняем в ChromaDB (с встроенными эмбеддингами)
print("💾 Сохраняем в ChromaDB...")
client = chromadb.PersistentClient(path="./chroma_db")

# Удаляем старую коллекцию, если есть
try:
    client.delete_collection("taskflow_docs")
except:
    pass

collection = client.create_collection(
    name="taskflow_docs",
    metadata={"hnsw:space": "cosine"},
)

# Добавляем чанки пачками
for i, chunk in enumerate(chunks):
    collection.add(
        ids=[f"chunk_{i}"],
        documents=[chunk.page_content],
        metadatas=[{"source": chunk.metadata.get("source", "unknown")}],
    )

print(f"   Сохранено в коллекцию: {collection.count()} чанков")

# 4. Тестируем поиск!
print("\n🔍 Тестируем поиск...")
test_queries = [
    "Как работает авторизация?",
    "Какие есть роли пользователей?",
    "Что делать если RabbitMQ не работает?",
    "Как запустить тесты?",
]

for query in test_queries:
    results = collection.query(query_texts=[query], n_results=3)
    print(f"\n❓ {query}")
    for j, (doc, meta) in enumerate(
        zip(results["documents"][0], results["metadatas"][0])
    ):
        source = meta["source"].split("\\")[-1]  # только имя файла
        print(f"   [{j+1}] ({source}) {doc[:100]}...")

print("\n✅ Готово! Индекс создан в ./chroma_db")