# RAG Knowledge Base — MCP-сервер с локальной LLM

MCP-сервер, который превращает папку с документами в базу знаний. Corrective RAG на LangGraph, ChromaDB, Ollama.

---

## Попробовать прямо сейчас

Готовый образ с демо-базой «Правила движения единорогов по Тилимилитрямдии» — никакой настройки, только Docker.

**Требования:** Docker Desktop + Claude Code (`npm install -g @anthropic-ai/claude-code`)

### Шаг 1 — Запустить

```bash
# CPU (универсальный)
docker run -d -p 8000:8000 -v pdd-ollama:/root/.ollama --name pdd-unicorn thejubadze/pdd-unicorn:latest

# NVIDIA GPU (быстрее в 10–20 раз)
# Сначала проверь, что GPU доступен в Docker:
#   nvidia-smi
#   docker run --rm --gpus all nvidia/cuda:12.3.2-base-ubuntu22.04 nvidia-smi
# Если оба показывают карту — запускай:
docker run -d -p 8000:8000 -v pdd-ollama:/root/.ollama --gpus all --name pdd-unicorn thejubadze/pdd-unicorn:latest
```

### Шаг 2 — Дождаться загрузки моделей (~5–15 мин при первом запуске)

```bash
docker logs -f pdd-unicorn
```

Ждать сообщения: `Модели готовы!`
После этого нажать `Ctrl+C` — контейнер продолжит работать в фоне.

> **Примечание:** ~2.7 GB моделей скачиваются только при первом запуске.
> При повторных запусках старт занимает несколько секунд.

### Шаг 3 — Подключить к Claude Code (один раз)

```bash
claude mcp add pdd-unicorn --transport sse http://localhost:8000/sse
```

### Шаг 4 — Спросить в Claude Code

Открыть VS Code → запустить Claude Code (`Ctrl+Shift+P` → "Claude: Open Chat") → задать вопрос.

Для надёжного вызова базы — упомяни инструмент явно:

```
Используй pdd-unicorn: какой сигнал подаёт единорог перед обгоном?
Используй pdd-unicorn: сколько рогосигналов существует и что они означают?
Используй pdd-unicorn: какие правила на звёздных развязках?
Используй pdd-unicorn: что запрещено делать с рогом во время движения?
Используй pdd-unicorn: опиши все типы дорог в Тилимилитрямдии
Используй pdd-unicorn: расскажи про лунные светофоры — как они работают?
```

Или без явного указания — Claude сам решит использовать базу по контексту:

```
По правилам движения Тилимилитрямдии — что такое радуготропа?
По правилам движения Тилимилитрямдии — что происходит при встречном разъезде на радуготропе?
```

Claude автоматически воспользуется базой знаний ПДД Тилимилитрямдии.

---

Образ на Docker Hub: [`thejubadze/pdd-unicorn`](https://hub.docker.com/r/thejubadze/pdd-unicorn)

---

## Возможности

- **Индексация документов** — .md, .txt, .py, .cs, .json и ещё 50+ форматов
- **Гибридный поиск** — векторный (ChromaDB) + ключевой (BM25) с RRF-слиянием
- **Corrective RAG** — переписывание запросов, фильтрация нерелевантных чанков, проверка на галлюцинации
- **MCP-интеграция** — работает с Claude Code и Claude Desktop

---

## Установка для своего проекта

Подробная пошаговая инструкция — [SETUP.md](SETUP.md).

**Коротко:**

```bash
git clone https://github.com/TheJubadze/OtusAiForDevs.git
cd OtusAiForDevs/RAG

python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements.txt

# Настроить .env и проиндексировать свои папки
copy .env.example .env
python index_my_project.py

# Подключить к Claude Code
claude mcp add rag-knowledge-base \
  -e CHROMA_PATH=./chroma_db \
  -e COLLECTION_NAME=my_project \
  -- python server.py
```

---

## Использование

### Вариант 1: Python API

```python
from rag import create_rag_chain, ask_question

chain, vector_store, llm = create_rag_chain(
    chroma_path="./chroma_db",
    collection_name="my_docs",
)

result = vector_store.index_folder("./my_documents", reset=True)
response = ask_question("Как работает авторизация?", chain=chain)
print(response["answer"])
```

### Вариант 2: MCP-сервер с Claude Desktop

Откройте файл конфигурации Claude Desktop:
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "rag-knowledge-base": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "C:\\path\\to\\RAG",
      "env": {
        "CHROMA_PATH": "./chroma_db",
        "COLLECTION_NAME": "documents",
        "LLM_MODEL": "qwen2.5:3b"
      }
    }
  }
}
```

### Вариант 3: Docker (своя база)

```bash
# С GPU (NVIDIA)
docker compose up -d

# Без GPU (CPU-only)
docker compose -f docker-compose.cpu.yml up -d

# Логи / остановка
docker compose logs -f rag-server
docker compose down
```

---

## MCP-инструменты

| Инструмент | Описание |
|------------|----------|
| `index_folder` | Индексирует папку в ChromaDB |
| `ask_question` | Полный Corrective RAG пайплайн |
| `find_relevant_docs` | Поиск без генерации ответа |
| `summarize_document` | Краткое содержание файла |
| `index_status` | Статус индекса |

Подробное описание с параметрами и примерами — ниже.

<details>
<summary>Подробнее о каждом инструменте</summary>

### index_folder

```
folder_path  (string, required) — путь к папке
chunk_size   (int, default=800) — размер чанка в символах
chunk_overlap(int, default=100) — перекрытие между чанками
reset        (bool, default=False) — пересоздать с нуля
```

### ask_question

```
question    (string, required) — вопрос на естественном языке
max_retries (int, default=2)   — максимум повторных попыток
```

### find_relevant_docs

```
query     (string, required) — поисковый запрос
n_results (int, default=5)   — количество результатов
```

### summarize_document

```
file_path (string, required) — путь к файлу
```

</details>

---

## Архитектура

Подробное описание — [ARCHITECTURE.md](ARCHITECTURE.md).

### Corrective RAG граф

```
START → rewrite_query → retrieve → grade_chunks → [conditional]
                                        │
                    ┌───────────────────┼───────────────────┐
                    ↓                   ↓                   ↓
              (has_relevant)      (no_relevant,        (no_relevant,
                    │              can_retry)          max_retries)
                    ↓                   ↓                   ↓
                generate          prepare_retry          finalize
                    │                   │                   │
                    ↓                   ↓                   ↓
          hallucination_check     rewrite_query           END
                    │                   ↑
           ┌───────┴───────┐            │
           ↓               ↓            │
       finalize      prepare_retry ─────┘
           │
           ↓
          END
```

### Структура проекта

```
RAG/
├── rag/                        # Модуль Corrective RAG
│   ├── state.py                # RAGState TypedDict
│   ├── utils.py                # VectorStore, LLM
│   ├── nodes.py                # Узлы графа
│   └── graph.py                # LangGraph граф
├── tests/                      # 42 pytest теста
├── sample_docs/                # 21 демо-документ
├── pdd_docs/                   # Тестовая база знаний (ПДД единорогов)
├── server.py                   # FastMCP сервер
├── index_my_project.py         # Скрипт индексации своих папок
├── docker-compose.pdd.yml      # Демо с единорогами (готовый образ)
├── docker-compose.yml          # GPU версия (своя база)
├── docker-compose.cpu.yml      # CPU версия (своя база)
├── .env.example                # Шаблон переменных окружения
├── SETUP.md                    # Пошаговая установка
├── ARCHITECTURE.md             # Архитектура
└── REPORT.md                   # История разработки
```

---

## Конфигурация

| Переменная | Default | Описание |
|------------|---------|----------|
| `OLLAMA_HOST` | `http://localhost:11434` | Адрес Ollama |
| `CHROMA_PATH` | `./chroma_db` | Путь к ChromaDB |
| `COLLECTION_NAME` | `documents` | Имя коллекции |
| `LLM_MODEL` | `qwen2.5:3b` | Модель LLM |
| `CHUNK_SIZE` | `800` | Размер чанка |
| `VECTOR_WEIGHT` | `0.3` | Вес векторного поиска (0–1) |

---

## Тестирование

```bash
pytest                                          # все тесты
pytest -v                                       # с подробным выводом
pytest tests/test_nodes.py                      # конкретный файл
pytest --cov=rag --cov=server --cov-report=html # с покрытием
```

---

## Troubleshooting

**Ollama не запускается**
```bash
ollama list
ollama pull nomic-embed-text
ollama pull qwen2.5:3b
```

**ChromaDB ошибка с Python 3.14** — используйте Python 3.12:
```bash
py -3.12 -m venv venv
```

**Медленная генерация** — нормально для CPU (10–30 с). Для ускорения:
```bash
ollama pull qwen2.5:1.5b
```

**Docker: модели не скачиваются**
```bash
docker logs pdd-unicorn
docker restart pdd-unicorn
```

---

## Лицензия

MIT

---

## Автор

Создано с помощью Claude Code (Sonnet 4.6) в рамках курса OTUS "AI for Developers".
