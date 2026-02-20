# Архитектура RAG Knowledge Base

## Обзор

RAG Knowledge Base — это MCP-сервер, который превращает папку с документами в интерактивную базу знаний. Система реализует паттерн **Corrective RAG (CRAG)** на базе LangGraph: запрос проходит через несколько LLM-проверок, прежде чем пользователь получает ответ.

```
Claude (Claude Code / Claude Desktop)
            │
            │  MCP (stdio)
            ▼
     ┌─────────────┐
     │  server.py  │  FastMCP — 5 инструментов
     └──────┬──────┘
            │
     ┌──────▼──────┐        ┌────────────┐
     │  rag/graph  │───────▶│  Ollama    │  LLM (qwen2.5:3b)
     │  LangGraph  │        │  Embeddings│  nomic-embed-text
     └──────┬──────┘        └────────────┘
            │
     ┌──────▼──────┐
     │  ChromaDB   │  Персистентное хранилище векторов
     └─────────────┘
```

---

## Слои системы

### 1. MCP-сервер (`server.py`)

Точка входа. Реализован на **FastMCP** и предоставляет 5 инструментов:

| Инструмент | Что делает | Использует LLM? |
|---|---|---|
| `index_folder` | Индексирует папку в ChromaDB | Нет (только эмбеддинги) |
| `find_relevant_docs` | Прямой векторный поиск, без генерации | Нет |
| `index_status` | Возвращает статус коллекции | Нет |
| `ask_question` | Полный Corrective RAG пайплайн | Да |
| `summarize_document` | Читает файл и суммаризирует | Да |

**Ленивая инициализация.** `VectorStore`, `LLM` и скомпилированный граф создаются только при первом обращении — это ускоряет старт сервера:

```python
class AppState:
    @property
    def vector_store(self) -> VectorStore:   # создаётся при первом вызове
    @property
    def llm(self) -> LLM:                   # создаётся при первом вызове
    @property
    def chain(self):                         # компилируется при первом вызове
```

---

### 2. Corrective RAG граф (`rag/graph.py`)

Построен на **LangGraph**. Граф компилируется один раз и переиспользуется для всех запросов.

#### Структура графа

```
START
  │
  ▼
rewrite_query ──────────────────────────────────┐
  │                                              │
  ▼                                             (retry)
retrieve                                         │
  │                                              │
  ▼                                              │
grade_chunks ──[has_relevant_docs?]──────────────┤
  │ да                    │ нет                  │
  ▼                       ▼                      │
generate            [retry_count < max?]         │
  │                  да │      │ нет             │
  ▼                    ▼       ▼                 │
hallucination     prepare  finalize              │
_check             _retry ──────────────────────┘
  │ нет
  ▼ галлюцинация?
finalize ──▶ END
```

#### Узлы и их логика

| Узел | Входные данные | Выходные данные | Промпт |
|---|---|---|---|
| `rewrite_query` | `original_query`, `retry_count` | `rewritten_query` | На первом проходе — уточнение; на повторных — синонимы |
| `retrieve` | `rewritten_query` | `retrieved_docs` (10 чанков) | — |
| `grade_chunks` | `retrieved_docs`, `original_query` | `relevant_docs`, `has_relevant_docs` | JSON: `{"relevant": true/false}` |
| `generate` | `relevant_docs`, `original_query` | `answer`, `sources` | temperature=0.1, строгий запрет выдумок |
| `hallucination_check` | `answer`, `relevant_docs` | `is_hallucinated` | JSON: `{"grounded": true/false}` |
| `prepare_retry` | `retry_count` | сброс `retrieved_docs`, `relevant_docs`, `answer`; `retry_count += 1` | — |
| `finalize` | — | `error=None` | — |

#### State машина (`rag/state.py`)

```python
class RAGState(TypedDict):
    original_query: str        # исходный вопрос пользователя
    rewritten_query: str       # переписанный для поиска
    retrieved_docs: List[Document]   # сырые результаты поиска
    relevant_docs:  List[Document]   # после LLM-фильтрации
    answer: str                # сгенерированный ответ
    has_relevant_docs: bool    # флаг: нашли хоть что-то релевантное?
    is_hallucinated: bool      # флаг: ответ не основан на контексте?
    retry_count: int           # текущая попытка (от 0)
    max_retries: int           # лимит попыток (default: 2)
    sources: List[str]         # имена файлов-источников
    error: Optional[str]
```

---

### 3. Векторное хранилище (`rag/utils.py — VectorStore`)

#### Индексация

```
Папка с файлами
    │
    ▼ scan (rglob)
Фильтрация файлов:
  - расширения из TEXT_EXTENSIONS (~50 типов)
  - пропуск SKIP_DIRS (node_modules, __pycache__, .git, ...)
  - пропуск SKIP_FILENAMES (package-lock.json, ...)
  - пропуск SKIP_SUFFIXES (.min.js, .generated.cs, ...)
  - пропуск файлов > 100 KB
    │
    ▼ TextLoader (UTF-8 → autodetect)
Загрузка документов
    │
    ▼ RecursiveCharacterTextSplitter
Разбивка на чанки:
  chunk_size=800, overlap=100
  separators: ["\n## ", "\n### ", "\n\n", "\n", " "]
    │
    ▼ батчи по 200 чанков
Эмбеддинги через Ollama (nomic-embed-text)
    │
    ▼
ChromaDB PersistentClient
  collection: hnsw, cosine distance
```

#### Гибридный поиск (Hybrid Search)

При каждом запросе `retrieve` вызывает `hybrid_search`:

```
Запрос
  ├──▶ Vector Search (ChromaDB, n*2=20 кандидатов)
  │    cosine similarity на эмбеддингах
  │
  └──▶ BM25 Search (rank-bm25, n*2=20 кандидатов)
       токенизация + стемминг (snowballstemmer, russian)

       Объединение через Reciprocal Rank Fusion (RRF, k=60):
         score = vector_weight × rrf_vector + bm25_weight × rrf_bm25
         vector_weight = 0.3   (VECTOR_WEIGHT env var)
         bm25_weight   = 0.7

       → топ 10 чанков по combined score → retrieved_docs
```

BM25-индекс строится **лениво** при первом поиске и кешируется в памяти на время жизни процесса.

---

### 4. LLM-обёртка (`rag/utils.py — LLM`)

```python
class LLM:
    def generate(prompt, temperature=0.1) -> str:
        # Ollama chat API

    def generate_json(prompt, temperature=0.0) -> str:
        # Ollama с format="json" — гарантирует валидный JSON
```

Используется в `grade_chunks` и `hallucination_check` для структурированных ответов (`generate_json`), и в остальных узлах для свободного текста (`generate`).

---

## Конфигурация

Все параметры читаются из переменных окружения при старте:

| Переменная | Default | Где используется |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | VectorStore, LLM |
| `CHROMA_PATH` | `./chroma_db` | VectorStore |
| `COLLECTION_NAME` | `documents` | VectorStore |
| `LLM_MODEL` | `qwen2.5:3b` | LLM |
| `CHUNK_SIZE` | `800` | VectorStore.index_folder |
| `CHUNK_OVERLAP` | `100` | VectorStore.index_folder |
| `BATCH_SIZE` | `200` | VectorStore.index_folder |
| `VECTOR_WEIGHT` | `0.3` | VectorStore.hybrid_search |
| `STEMMER_LANG` | `russian` | VectorStore._tokenize |

---

## Структура модулей

```
rag/
├── __init__.py      # реэкспорт create_rag_chain, ask_question, VectorStore, LLM
├── state.py         # RAGState TypedDict, Document TypedDict
├── utils.py         # VectorStore (ChromaDB + BM25), LLM (Ollama)
├── nodes.py         # все узлы графа (фабрика create_nodes)
└── graph.py         # сборка графа, build_graph(), create_rag_chain(), ask_question()
server.py            # FastMCP сервер, AppState, 5 инструментов
```

---

## Ключевые архитектурные решения

**Corrective RAG вместо простого RAG.**
Стандартный RAG делает один поиск и генерирует ответ. CRAG добавляет три проверки: релевантность чанков, возможность ретрая с переформулировкой, и детектор галлюцинаций. Это увеличивает качество ответов на "сложных" запросах, но требует локальную LLM.

**Гибридный поиск (BM25 + vector).**
Чистый векторный поиск плохо работает на точных совпадениях (имена, аббревиатуры, специфические термины). BM25 закрывает этот пробел. RRF-слияние позволяет комбинировать оба сигнала без нормализации скоров.

**Промпт grade_chunks использует тематическое соответствие, а не полезность.**
Маленькая 3B-модель при вопросе "этот чанк полезен для ответа?" часто отвечает "нет" на документах со специфической терминологией. Критерий "относится ли к той же теме?" значительно устойчивее.

**JSON structured output через Ollama format="json".**
Узлы `grade_chunks` и `hallucination_check` обязаны вернуть булев флаг. Ollama с `format="json"` гарантирует парсируемый JSON и устраняет проблему "модель вставляет текст перед JSON".

**Ленивая инициализация в AppState.**
ChromaDB и Ollama-клиент создаются только при первом обращении к инструменту. Это позволяет MCP-серверу быстро ответить на handshake, не блокируясь на инициализации тяжёлых компонентов.
