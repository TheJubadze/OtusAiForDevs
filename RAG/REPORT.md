# REPORT — История создания RAG Knowledge Base

## Описание проекта

MCP-сервер, который превращает локальную папку с документами в поисковую базу знаний. Внутри — RAG-пайплайн на LangGraph с локальной LLM через Ollama.

**Стек:** Python, FastMCP, LangGraph, LangChain, ChromaDB, Ollama (qwen2.5:3b + nomic-embed-text)

---

## Этап 1: Изучение задания и планирование

### Промпт 1 — Разбор задания
> **Я:** У меня есть задание (прикреплён PDF). Читай с места "RAG Knowledge Base — MCP-сервер с локальной LLM и LangGraph". Я не понимаю, с чего начать. У меня на работе большой проект и Wiki на Azure DevOps — хочу засунуть это всё в базу данных. Помоги разобраться.

**Результат:** Получил подробное объяснение:
- Как работает RAG (индексация → поиск → генерация)
- Что конкретно нужно по заданию (MCP-сервер, 5 инструментов, LangGraph граф, Ollama, Docker)
- Пошаговый план на 3 недели
- Совет про Azure DevOps Wiki — это Git-репозиторий с .md файлами, можно склонировать

### Промпт 2 — Как достать Wiki из Azure DevOps
> **Я:** Можно подробнее про Azure DevOps Wiki? Как мне её достать?

**Результат:** Узнал два способа:
- `git clone` через URL из кнопки "Clone wiki" в интерфейсе
- Через Personal Access Token для автоматизации
- Структура Wiki: обычные .md файлы в папках, пробелы заменены на дефисы

### Промпт 3 — На чём тренироваться
> **Я:** Предложи, на чём потренироваться? Какой взять репозиторий, вики или что-то ещё?

**Результат:** Три варианта:
1. FastAPI — ~100 .md файлов документации + Python код
2. LangChain — документация инструмента, который сам используешь
3. **Своя мини-Wiki** (выбрал этот вариант) — 15–20 файлов имитирующих рабочую документацию

**Решение:** Начать с собственных demo-документов — контролируемый набор, можно проверить правильность ответов.

---

## Этап 2: Подготовка demo-документов

### Промпт 4 — Генерация sample_docs
> **Я:** Да, хочу [сгенерировать sample_docs]

**Результат:** Claude сгенерировал набор из **21 файла (~2300 строк)** — имитация внутренней документации вымышленного проекта "TaskFlow":

**Структура:**
```
sample_docs/
├── architecture.md          # Микросервисная архитектура
├── auth_flow.md             # JWT авторизация
├── database_schema.md       # Схема БД (PostgreSQL)
├── notification_service.md  # Сервис уведомлений
├── docker_compose.md        # Docker конфигурация
├── env_reference.md         # Переменные окружения
├── security.md              # Безопасность
├── changelog.md             # История изменений
├── api/
│   ├── task_api.md          # API задач
│   └── auth_api.md          # API авторизации
├── guides/
│   ├── onboarding.md        # Онбординг разработчика
│   ├── coding_standards.md  # Стандарты кода
│   ├── deployment.md        # Процесс деплоя
│   ├── testing.md           # Тестирование
│   ├── troubleshooting.md   # Решение проблем
│   ├── monitoring.md        # Мониторинг
│   └── sprint_workflow.md   # Спринты и Scrum
└── code/
    ├── task_service.py      # Пример Python-кода
    ├── config.py            # Конфигурация
    ├── event_publisher.py   # Публикация событий в RabbitMQ
    └── kong.yaml            # Конфиг API Gateway
```

**Ключевое:** Документы связаны между собой — auth_flow.md ссылается на database_schema.md, код использует паттерны из coding_standards.md. Это позволяет тестировать поиск по нескольким файлам.

Файлы распакованы в `D:\Dev\OtusAiForDevs\RAG\sample_docs\`.

---

## Этап 3: Установка инструментов

### Промпт 5 — С чего начать
> **Я:** Распаковал каталог в D:\Dev\OtusAiForDevs\RAG\. Что делать теперь?

**Шаги выполнены:**

1. **Установка Ollama** — скачал с https://ollama.com/download (Windows)
2. **Скачивание моделей:**
   ```bash
   ollama pull qwen2.5:3b          # LLM для генерации (~2.4 GB)
   ollama pull nomic-embed-text     # Модель эмбеддингов (~274 MB)
   ```
3. **Проверка:** `ollama run qwen2.5:3b "Скажи привет"` — работает

### Проблема: Python 3.14 несовместим с ChromaDB

```
pydantic.v1.errors.ConfigError: unable to infer type for attribute "chroma_server_nofile"
```

**Причина:** Установлен Python 3.14 (preview), ChromaDB его не поддерживает.

**Решение:**
- Скачал Python 3.12.8 с python.org
- Пересоздал виртуальное окружение: `py -3.12 -m venv venv`
- Установил зависимости:
  ```bash
  pip install chromadb langchain langchain-community langchain-core langgraph ollama langchain-text-splitters
  ```

**Примечание:** `pyenv` на Windows не установлен, использовал `py -3.12` (Python Launcher).

**Проверка:**
```bash
python -c "import chromadb; import langchain; print('OK')"
# OK
```

---

## Этап 4: Первый скрипт индексации (test_index.py)

### Промпт 6 — Скрипт индексации
> Claude предоставил скрипт `test_index.py`

**Что делает скрипт:**
1. Загружает 21 файл из `sample_docs/` через `DirectoryLoader`
2. Разбивает на чанки по 500 символов (`RecursiveCharacterTextSplitter`)
3. Сохраняет в ChromaDB с дефолтными эмбеддингами (`all-MiniLM-L6-v2`)
4. Тестирует поиск по 4 вопросам

### Проблема: устаревший импорт
```
ModuleNotFoundError: No module named 'langchain.text_splitter'
```
**Решение:** В новых версиях LangChain модуль переехал:
```python
# Было:
from langchain.text_splitter import RecursiveCharacterTextSplitter
# Стало:
from langchain_text_splitters import RecursiveCharacterTextSplitter
```
Плюс `pip install langchain-text-splitters`.

### Результат
- Загружено 21 файл → 203 чанка
- При первом запуске ChromaDB скачивает модель `all-MiniLM-L6-v2` (~80 MB, ~18 минут)
- Поиск работает, но качество низкое — на вопрос "Как работает авторизация?" находит `sprint_workflow.md` вместо `auth_flow.md`

**Причина плохого качества:** Дефолтная модель `all-MiniLM-L6-v2` плохо понимает русский язык.

---

## Этап 5: Полный RAG с LLM (test_rag.py)

Подключена генерация ответов через Ollama (qwen2.5:3b).

### Результат
- Авторизация: "информация недоступна" ❌ (поиск не нашёл нужные чанки)
- RabbitMQ: частично верный ответ, нашёл troubleshooting.md ✅
- Роли: "admin может назначать задачи" — слишком скудно ❌
- Тесты: "информации нет" ❌

**Вывод:** Проблема в поиске (дефолтные эмбеддинги), а не в LLM.

---

## Этап 6: Ollama-эмбеддинги (test_rag_v2.py)

### Промпт 7 — Улучшение эмбеддингов
> Claude предложил перейти на `nomic-embed-text` через Ollama

**Ключевое изменение:**
```python
ollama_ef = ef.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text",
)
```

### Результат — заметное улучшение
- Авторизация: ✅ нашёл `auth_flow.md`, ответ про JWT верный
- RabbitMQ: частично ✅ нашёл `troubleshooting.md`, но LLM добавила лишние советы (галлюцинация)
- Роли: ❌ выдумала "исторический инженер"
- Тесты: ❌ не нашёл `testing.md`

---

## Этап 7: Увеличенные чанки + строгий промпт (test_rag_v3.py)

### Изменения
1. **Размер чанков:** 500 → 1000 символов (меньше разрезанных разделов)
2. **Overlap:** 50 → 100 символов
3. **Строгий промпт:**
   ```
   СТРОГИЕ ПРАВИЛА:
   1. Отвечай ТОЛЬКО на основе контекста
   2. Если нет информации — скажи об этом
   3. НЕ ВЫДУМЫВАЙ информацию
   ```
4. Добавлен вывод найденных источников для отладки
5. Добавлен тестовый вопрос "Какой пароль у admin?" (проверка конкретных фактов)

### Результат
- Чанков стало меньше: 203 → 104 (чанки крупнее и содержательнее)
- Авторизация: ✅ правильный ответ, нашёл auth_flow.md
- Пароль admin: ✅ точный ответ `Admin123!` из onboarding.md
- Тесты: нашёл testing.md ✅, но LLM выдумала команды (`python manage.py migrate`)
- RabbitMQ: нашёл troubleshooting.md ✅, но ответ содержит галлюцинации
- Роли: ❌ не нашёл auth_flow.md, сказал "информация не найдена"

**Вывод:** Поиск стал значительно лучше, но LLM (3B параметров) галлюцинирует. Нужен Corrective RAG с проверками.

---

## Этап 8: Переход к Claude Code

### Промпт 8 — Перенос в VS Code
> **Я:** Можем ли мы перенести диалог в плагин Claude для VS Code?

**Ответ:** Историю перенести нельзя, но можно:
1. **Claude Code (CLI)** — работает в терминале VS Code, видит файлы, может редактировать и запускать
2. Продолжить в claude.ai
3. Начать новый диалог в VS Code расширении

**Решение:** Установлен Claude Code (`npm install -g @anthropic-ai/claude-code`), модель Opus 4.5.

### Промпт для передачи контекста в Claude Code:
```
Я делаю учебный проект — RAG MCP-сервер на Python.
Стек: LangGraph, ChromaDB, Ollama (qwen2.5:3b + nomic-embed-text), FastMCP.

Что уже сделано:
- В папке sample_docs/ лежат 21 демо-документ
- Базовый RAG работает: test_rag_v3.py
- Рабочий скрипт: индексация + поиск + генерация ответов

Что нужно сделать:
1. LangGraph граф (Corrective RAG)
2. MCP-сервер (FastMCP) с 5 инструментами
3. Docker Compose
4. Тесты (минимум 10)
```

---

## Следующие шаги (запланированы)

1. **LangGraph граф (Corrective RAG):**
   - Rewrite query → Retrieve → Grade chunks → Generate → Hallucination check
   - Условные переходы и retry-циклы

2. **MCP-сервер (FastMCP) — 5 инструментов:**
   - `index_folder` — индексация папки
   - `ask_question` — полный RAG-пайплайн
   - `find_relevant_docs` — поиск без генерации
   - `summarize_document` — саммари файла
   - `index_status` — статистика индекса

3. **Docker Compose** — сервер + Ollama одной командой

4. **Тесты** — минимум 10 (unit + integration + e2e)

---

## Ключевые уроки и наблюдения

### Удачные решения
- **Начать с малого:** Простой скрипт → добавление LLM → улучшение эмбеддингов → улучшение чанков. Каждый шаг проверяем.
- **Demo-документы:** Создание собственных контролируемых документов вместо случайного open-source репо — можно точно проверить правильность ответов.
- **Ollama эмбеддинги (nomic-embed-text):** Дефолтная модель ChromaDB плохо работает с русским текстом. Переход на nomic-embed-text дал заметное улучшение.

### Проблемы и их решения
| Проблема | Решение |
|----------|---------|
| Python 3.14 несовместим с ChromaDB | Установить Python 3.12, пересоздать venv |
| `langchain.text_splitter` не найден | Импорт из `langchain_text_splitters` + pip install |
| Дефолтные эмбеддинги плохо ищут по русскому тексту | Заменить на `nomic-embed-text` через Ollama |
| LLM галлюцинирует (выдумывает факты) | Строгий промпт + нужен Corrective RAG (LangGraph) |
| Маленькие чанки (500 сим.) разрезают разделы | Увеличить до 1000 символов |

### Неудачные промпты / подходы
- Дефолтный промпт без строгих ограничений — LLM свободно галлюцинирует, выдумывая "исторического инженера" и несуществующие команды
- Маленькие чанки (500 символов) — теряется контекст, разделы документов разрезаются пополам

---

## Этап 9: LangGraph Corrective RAG

### Промпт 9 — Создание LangGraph графа
> **Я (в Claude Code):** Начни с LangGraph графа. Посмотри test_rag_v3.py чтобы понять текущую реализацию.

**Результат:** Claude Code создал модульную структуру Corrective RAG:

```
rag/
├── __init__.py      # Экспорты модуля
├── state.py         # RAGState TypedDict — состояние графа
├── utils.py         # VectorStore (ChromaDB), LLM (Ollama)
├── nodes.py         # Функции узлов графа
└── graph.py         # Сборка и компиляция графа LangGraph
```

### Архитектура графа

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

### Узлы графа (nodes.py)

| Узел | Описание |
|------|----------|
| `rewrite_query` | Переписывает запрос для улучшения поиска. При retry использует синонимы |
| `retrieve` | Поиск в ChromaDB через VectorStore (5 чанков) |
| `grade_chunks` | LLM оценивает релевантность каждого чанка (JSON: `{"relevant": true/false}`) |
| `generate` | Генерация ответа на основе релевантных чанков |
| `hallucination_check` | LLM проверяет, основан ли ответ на контексте |
| `prepare_retry` | Увеличивает счётчик retry, сбрасывает состояние |
| `finalize` | Финализация результата |

### Состояние графа (state.py)

```python
class RAGState(TypedDict):
    original_query: str          # Исходный вопрос
    rewritten_query: str         # Переписанный запрос
    retrieved_docs: List[Document]   # Найденные документы
    relevant_docs: List[Document]    # Релевантные после фильтрации
    answer: str                  # Сгенерированный ответ
    has_relevant_docs: bool      # Есть ли релевантные документы
    is_hallucinated: bool        # Галлюцинация обнаружена
    retry_count: int             # Текущая попытка
    max_retries: int             # Максимум попыток (default: 2)
    sources: List[str]           # Источники ответа
    error: Optional[str]         # Ошибка если есть
```

### Утилиты (utils.py)

**VectorStore** — обёртка над ChromaDB:
- `index_folder(path, chunk_size, reset)` — индексация папки
- `search(query, n_results)` — поиск документов
- `get_status()` — статистика индекса

**LLM** — обёртка над Ollama:
- `generate(prompt, temperature)` — генерация текста
- `generate_json(prompt)` — генерация с `format="json"`

### Использование

```python
from rag import create_rag_chain, ask_question

# Создание цепочки
chain, vector_store, llm = create_rag_chain(
    chroma_path="./chroma_db",
    collection_name="docs",
)

# Индексация
vector_store.index_folder("./sample_docs", reset=True)

# Вопрос
result = ask_question("Как работает авторизация?", chain=chain)
print(result["answer"])
print(result["sources"])
```

### Также добавлено

- **requirements.txt** — зависимости проекта:
  ```
  langgraph>=0.2.0
  langchain>=0.3.0
  chromadb>=0.5.0
  ollama>=0.3.0
  fastmcp>=0.1.0
  pytest>=8.0.0
  ```

- **test_langgraph.py** — тестовый скрипт для проверки графа

- **.gitignore** — игнорирование venv, chroma_db*, __pycache__ и т.д.

### Ключевые особенности Corrective RAG

1. **Query Rewriting** — LLM переписывает запрос для улучшения поиска
2. **Chunk Grading** — LLM оценивает релевантность каждого чанка (не все найденные используются)
3. **Hallucination Check** — проверка, что ответ основан на контексте
4. **Retry Logic** — при отсутствии релевантных документов или галлюцинации — повторный поиск с переформулированным запросом (до 2 попыток)

---

## Следующие шаги

1. **MCP-сервер (FastMCP) — 5 инструментов:**
   - `index_folder` — индексация папки
   - `ask_question` — полный RAG-пайплайн
   - `find_relevant_docs` — поиск без генерации
   - `summarize_document` — саммари файла
   - `index_status` — статистика индекса

2. **Docker Compose** — сервер + Ollama одной командой

3. **Тесты** — минимум 10 (unit + integration + e2e)