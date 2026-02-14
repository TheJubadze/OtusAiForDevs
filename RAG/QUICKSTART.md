# Быстрый старт: RAG для вашего репозитория

Пошаговая инструкция как создать базу знаний из любой папки с документами и начать задавать вопросы.

---

## Шаг 1: Установка (один раз)

### 1.1 Установите Ollama

Скачайте с https://ollama.com/download и установите.

### 1.2 Скачайте модели

Откройте терминал и выполните:

```bash
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

Это займёт ~5-10 минут (скачивается ~2.7 GB).

### 1.3 Склонируйте RAG и установите зависимости

```bash
git clone https://github.com/TheJubadze/OtusAiForDevs.git
cd OtusAiForDevs/RAG

# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Шаг 2: Индексация вашего репозитория

### 2.1 Создайте скрипт `my_rag.py`

В папке `RAG/` создайте файл `my_rag.py`:

```python
from rag import create_rag_chain, ask_question

# 1. Создаём RAG
chain, vector_store, llm = create_rag_chain(
    chroma_path="./my_chroma_db",      # Где хранить индекс
    collection_name="my_project",       # Название коллекции
)

# 2. Индексируем папку (укажите путь к вашему репозиторию)
print("Индексация...")
result = vector_store.index_folder(
    "C:/path/to/your/repo",  # <-- ЗАМЕНИТЕ НА ПУТЬ К ВАШЕЙ ПАПКЕ
    reset=True,              # True = пересоздать индекс с нуля
)
print(f"Готово! Проиндексировано {result['chunks_indexed']} чанков")

# 3. Задаём вопросы
while True:
    question = input("\n❓ Ваш вопрос (или 'выход'): ")
    if question.lower() in ['выход', 'exit', 'q']:
        break

    result = ask_question(question, chain=chain)
    print(f"\n💬 {result['answer']}")
    if result['sources']:
        print(f"📎 Источники: {', '.join(result['sources'])}")
```

### 2.2 Запустите

```bash
python my_rag.py
```

### 2.3 Задавайте вопросы

```
Индексация...
Готово! Проиндексировано 156 чанков

❓ Ваш вопрос (или 'выход'): Как работает авторизация?

💬 Авторизация реализована через JWT токены...
📎 Источники: auth.py, README.md

❓ Ваш вопрос (или 'выход'): выход
```

---

## Пример: индексация Azure DevOps Wiki

```bash
# 1. Склонируйте Wiki
git clone https://dev.azure.com/your-org/your-project/_git/your-project.wiki
```

```python
# 2. В my_rag.py укажите путь
result = vector_store.index_folder(
    "C:/repos/your-project.wiki",
    reset=True,
)
```

---

## Пример: индексация GitHub репозитория

```bash
# 1. Склонируйте репозиторий
git clone https://github.com/user/repo.git
```

```python
# 2. В my_rag.py укажите путь
result = vector_store.index_folder(
    "C:/repos/repo",
    reset=True,
)
```

---

## Частые вопросы

### Какие файлы индексируются?

Все текстовые файлы: `.md`, `.txt`, `.py`, `.js`, `.ts`, `.java`, `.go`, `.yaml`, `.json` и т.д.

### Как переиндексировать после изменений?

Запустите скрипт снова с `reset=True` — старый индекс удалится и создастся новый.

### Где хранится индекс?

В папке, которую вы указали в `chroma_path` (по умолчанию `./my_chroma_db`).

### Как изменить размер чанков?

```python
result = vector_store.index_folder(
    "C:/path/to/repo",
    chunk_size=1500,      # Больше контекста в каждом чанке
    chunk_overlap=200,    # Больше перекрытие
    reset=True,
)
```

### Медленно генерирует ответы?

На CPU это нормально (10-30 сек). Для ускорения:
- Используйте GPU (NVIDIA)
- Или меньшую модель: `ollama pull qwen2.5:1.5b` и в коде `LLM_MODEL=qwen2.5:1.5b`

---

## Готовый скрипт с настройками

```python
"""
RAG для вашего репозитория.
Использование: python my_rag.py
"""

from rag import create_rag_chain, ask_question

# ============ НАСТРОЙКИ ============
REPO_PATH = "C:/path/to/your/repo"  # <-- Путь к вашей папке
INDEX_PATH = "./my_chroma_db"        # Где хранить индекс
COLLECTION = "my_docs"               # Название коллекции
REINDEX = True                       # True = пересоздать индекс
# ===================================

def main():
    # Создание RAG
    print("🚀 Запуск RAG...")
    chain, vector_store, llm = create_rag_chain(
        chroma_path=INDEX_PATH,
        collection_name=COLLECTION,
    )

    # Индексация
    if REINDEX:
        print(f"📂 Индексация {REPO_PATH}...")
        result = vector_store.index_folder(REPO_PATH, reset=True)
        print(f"✅ Проиндексировано: {result['chunks_indexed']} чанков")
    else:
        status = vector_store.get_status()
        print(f"📊 Используем существующий индекс: {status['total_chunks']} чанков")

    # Интерактивный режим
    print("\n" + "="*50)
    print("Задавайте вопросы. Для выхода введите 'q' или 'выход'.")
    print("="*50)

    while True:
        question = input("\n❓ Вопрос: ").strip()

        if not question:
            continue
        if question.lower() in ['q', 'quit', 'exit', 'выход']:
            print("👋 До свидания!")
            break

        print("🔍 Ищу ответ...")
        result = ask_question(question, chain=chain)

        if result.get('error'):
            print(f"❌ Ошибка: {result['error']}")
        else:
            print(f"\n💬 {result['answer']}")
            if result['sources']:
                print(f"\n📎 Источники: {', '.join(result['sources'])}")


if __name__ == "__main__":
    main()
```

---

## Итого: 3 команды для старта

```bash
# 1. Один раз: установка моделей
ollama pull qwen2.5:3b && ollama pull nomic-embed-text

# 2. Один раз: установка Python зависимостей
pip install -r requirements.txt

# 3. Запуск RAG (отредактируйте REPO_PATH в скрипте)
python my_rag.py
```
