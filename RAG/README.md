# RAG Knowledge Base — MCP-сервер с локальной LLM

MCP-сервер, который превращает локальную папку с документами в поисковую базу знаний. Внутри — Corrective RAG на LangGraph с локальной LLM через Ollama.

## Возможности

- **Индексация документов** — загрузка .md, .txt, .py и других текстовых файлов в векторную базу
- **Умный поиск** — семантический поиск по содержимому документов
- **Генерация ответов** — ответы на вопросы на основе найденных документов
- **Corrective RAG** — переписывание запросов, оценка релевантности, проверка на галлюцинации
- **MCP-интеграция** — работает с Claude Desktop и другими MCP-клиентами

## Требования

- Python 3.12+
- [Ollama](https://ollama.com/download) (для локальных LLM)
- Docker (опционально, для контейнеризации)

---

## Быстрый старт

### 1. Установка Ollama

Скачайте и установите Ollama: https://ollama.com/download

```bash
# Проверка установки
ollama --version

# Скачивание моделей
ollama pull qwen2.5:3b          # LLM для генерации (~2.4 GB)
ollama pull nomic-embed-text     # Модель эмбеддингов (~274 MB)
```

### 2. Установка зависимостей Python

```bash
# Клонирование репозитория
git clone https://github.com/TheJubadze/OtusAiForDevs.git
cd OtusAiForDevs/RAG

# Создание виртуального окружения
python -m venv venv

# Активация (Windows)
venv\Scripts\activate

# Активация (Linux/macOS)
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

### 3. Проверка работы

```bash
# Запуск тестов
python -m pytest tests/ -v
```

---

## Использование

### Вариант 1: Python API

```python
from rag import create_rag_chain, ask_question

# Создание RAG цепочки
chain, vector_store, llm = create_rag_chain(
    chroma_path="./chroma_db",
    collection_name="my_docs",
)

# Индексация папки с документами
result = vector_store.index_folder("./my_documents", reset=True)
print(f"Проиндексировано: {result['chunks_indexed']} чанков")

# Задать вопрос
response = ask_question("Как работает авторизация?", chain=chain)
print(response["answer"])
print(f"Источники: {response['sources']}")
```

### Вариант 2: MCP-сервер с Claude Desktop

#### Шаг 1: Настройка Claude Desktop

Откройте файл конфигурации Claude Desktop:
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

Добавьте конфигурацию сервера:

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

> **Важно:** Замените `C:\\path\\to\\RAG` на реальный путь к папке проекта.

#### Шаг 2: Перезапустите Claude Desktop

После изменения конфигурации перезапустите Claude Desktop.

#### Шаг 3: Использование инструментов

В чате Claude Desktop станут доступны 5 инструментов:

| Инструмент | Пример использования |
|------------|---------------------|
| `index_folder` | "Проиндексируй папку C:\docs" |
| `ask_question` | "Как работает авторизация в системе?" |
| `find_relevant_docs` | "Найди документы про API" |
| `summarize_document` | "Сделай саммари файла architecture.md" |
| `index_status` | "Покажи статус индекса" |

### Вариант 3: Docker Compose

```bash
# С GPU (NVIDIA)
docker compose up -d

# Без GPU (CPU-only)
docker compose -f docker-compose.cpu.yml up -d

# Просмотр логов
docker compose logs -f rag-server

# Остановка
docker compose down
```

При первом запуске автоматически скачиваются модели Ollama (~2.7 GB).

---

## MCP-инструменты

### index_folder

Индексирует папку с документами в векторную базу данных.

```
Параметры:
- folder_path (string, required): Путь к папке с документами
- chunk_size (int, default=1000): Размер чанка в символах
- chunk_overlap (int, default=100): Перекрытие между чанками
- reset (bool, default=False): Пересоздать индекс с нуля

Возвращает: Статистику индексации
```

**Пример:**
```
> Проиндексируй папку ./sample_docs с нуля

Индексация завершена:
- Загружено документов: 21
- Создано чанков: 104
- Всего в индексе: 104
```

### ask_question

Задаёт вопрос по индексированным документам (полный RAG-пайплайн).

```
Параметры:
- question (string, required): Вопрос на естественном языке
- max_retries (int, default=2): Максимум повторных попыток

Возвращает: Ответ с указанием источников
```

**Пример:**
```
> Как работает авторизация в системе?

Авторизация реализована через JWT токены. Access token живёт 15 минут,
refresh token — 7 дней. При истечении access token клиент должен
обновить его через endpoint /auth/refresh.

📎 Источники: auth_flow.md, auth_api.md
```

### find_relevant_docs

Ищет релевантные документы без генерации ответа.

```
Параметры:
- query (string, required): Поисковый запрос
- n_results (int, default=5): Количество результатов

Возвращает: Список документов с превью
```

**Пример:**
```
> Найди документы про RabbitMQ

1. **troubleshooting.md** (score: 0.89)
   ## RabbitMQ не принимает сообщения Проверьте: 1. Статус сервиса...

2. **notification_service.md** (score: 0.76)
   Сервис уведомлений использует RabbitMQ для асинхронной обработки...
```

### summarize_document

Создаёт краткое содержание документа.

```
Параметры:
- file_path (string, required): Путь к файлу документа

Возвращает: Краткое содержание
```

**Пример:**
```
> Сделай саммари файла ./sample_docs/architecture.md

📄 **architecture.md**

• Микросервисная архитектура с 5 основными сервисами
• API Gateway на Kong для маршрутизации и rate limiting
• PostgreSQL как основная БД, Redis для кэширования
• RabbitMQ для асинхронного взаимодействия между сервисами
• Kubernetes для оркестрации в production
```

### index_status

Показывает статус индекса.

```
Параметры: нет

Возвращает: Информацию о состоянии индекса
```

**Пример:**
```
> Покажи статус индекса

📊 Статус индекса:
- Коллекция: documents
- Чанков в индексе: 104
- Путь к базе: ./chroma_db
```

---

## Архитектура

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

### Узлы графа

| Узел | Описание |
|------|----------|
| `rewrite_query` | LLM переписывает запрос для улучшения поиска |
| `retrieve` | Поиск в ChromaDB (5 чанков) |
| `grade_chunks` | LLM оценивает релевантность каждого чанка |
| `generate` | Генерация ответа на основе релевантных чанков |
| `hallucination_check` | LLM проверяет, основан ли ответ на контексте |
| `prepare_retry` | Подготовка к повторной попытке |
| `finalize` | Финализация результата |

### Структура проекта

```
RAG/
├── rag/                        # Модуль Corrective RAG
│   ├── __init__.py
│   ├── state.py                # RAGState TypedDict
│   ├── utils.py                # VectorStore, LLM
│   ├── nodes.py                # Узлы графа
│   └── graph.py                # LangGraph граф
├── tests/                      # 42 pytest теста
│   ├── conftest.py             # Фикстуры
│   ├── test_state.py
│   ├── test_utils.py
│   ├── test_nodes.py
│   ├── test_graph.py
│   └── test_server.py
├── sample_docs/                # 21 демо-документ
├── server.py                   # FastMCP сервер
├── pyproject.toml              # Конфигурация пакета и pytest
├── Dockerfile
├── docker-compose.yml          # GPU версия
├── docker-compose.cpu.yml      # CPU версия
├── requirements.txt
├── QUICKSTART.md               # Инструкция для быстрого старта
├── REPORT.md                   # История разработки
└── README.md                   # Эта инструкция
```

---

## Конфигурация

### Переменные окружения

| Переменная | Default | Описание |
|------------|---------|----------|
| `OLLAMA_HOST` | `http://localhost:11434` | Адрес Ollama сервера |
| `CHROMA_PATH` | `./chroma_db` | Путь к базе ChromaDB |
| `COLLECTION_NAME` | `documents` | Имя коллекции |
| `LLM_MODEL` | `qwen2.5:3b` | Модель LLM |

### Параметры индексации

| Параметр | Default | Описание |
|----------|---------|----------|
| `chunk_size` | 1000 | Размер чанка в символах |
| `chunk_overlap` | 100 | Перекрытие между чанками |

---

## Тестирование

```bash
# Запуск всех тестов
pytest

# С подробным выводом
pytest -v

# Конкретный файл
pytest tests/test_nodes.py

# С покрытием
pytest --cov=rag --cov=server --cov-report=html

# Только быстрые тесты (без интеграционных)
pytest -m "not integration"
```

---

## Troubleshooting

### Ollama не запускается

```bash
# Проверка статуса
ollama list

# Если пусто — скачайте модели
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

### ChromaDB ошибка с Python 3.14

ChromaDB не поддерживает Python 3.14. Используйте Python 3.12:

```bash
py -3.12 -m venv venv
```

### Медленная генерация ответов

- На CPU генерация занимает 10-30 секунд
- Для ускорения используйте GPU (NVIDIA) или меньшую модель:
  ```bash
  ollama pull qwen2.5:1.5b  # Быстрее, но менее точная
  ```

### Docker: модели не скачиваются

Проверьте, что контейнер `ollama` запущен и здоров:

```bash
docker compose ps
docker compose logs ollama
```

---

## Лицензия

MIT

---

## Автор

Создано с помощью Claude Code (Opus 4.5) в рамках курса OTUS "AI for Developers".
