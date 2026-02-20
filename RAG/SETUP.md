# Установка и настройка

Пошаговая инструкция «для чайников». Цель — установить систему на чистый Windows-компьютер,
проиндексировать рабочий проект и задавать вопросы через Claude в VS Code.

**Сценарий из этой инструкции:**

```
C:\git\MyProject\   — моно-репозиторий с большим проектом (.cs, .py, .md, .json, ...)
C:\git\wiki\        — репозиторий с вики-документацией (.md файлы)
```

## Выберите вариант

| | LITE (Рекомендуется) | FULL (Автономный) |
|---|---|---|
| Ollama модели | nomic-embed-text (274 MB) | nomic-embed-text + qwen2.5:3b (~2.7 GB) |
| Кто генерирует ответы | **Claude** (через VS Code) | **Локальная LLM** (qwen2.5:3b) |
| Качество ответов | **Высокое** | Среднее (3B модель галлюцинирует) |
| Доступные инструменты | 3 из 5 | Все 5 |
| Работает без интернета | Нет | Да |
| Время установки | ~20 мин | ~25 мин |

> **Рекомендуем LITE**, если работаете с Claude через VS Code и есть интернет.

---

## Шаг 1. Python 3.12

> ChromaDB не работает с Python 3.14. Нужна версия 3.11 или 3.12.

1. Скачайте Python 3.12 с https://www.python.org/downloads/release/python-3128/
2. При установке **обязательно** поставьте галочку **"Add Python to PATH"**
3. Проверьте:

```cmd
python --version
```

Ожидаемый вывод: `Python 3.12.x`

> Если у вас несколько версий Python, используйте `py -3.12` вместо `python` во всех командах ниже.

---

## Шаг 2. Ollama

Ollama — это программа, которая запускает языковые модели прямо на вашем компьютере.

1. Скачайте с https://ollama.com/download (Windows)
2. Установите и запустите
3. Откройте **новый** терминал и скачайте модели:

**LITE** — только модель эмбеддингов (274 MB):

```cmd
ollama pull nomic-embed-text
```

**FULL** — эмбеддинги + локальная LLM (~2.7 GB):

```cmd
ollama pull nomic-embed-text
ollama pull qwen2.5:3b
```

4. Проверьте:

```cmd
ollama list
```

> Ollama работает как фоновый сервис и автоматически запускается при старте Windows (иконка в трее).

---

## Шаг 3. Клонирование и установка

```cmd
cd C:\git
git clone https://github.com/TheJubadze/OtusAiForDevs.git
cd OtusAiForDevs\RAG
```

Создайте виртуальное окружение и установите зависимости:

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

> Если `python -m venv` не работает — попробуйте `py -3.12 -m venv venv`

*(FULL) Проверка — тесты должны пройти:*

```cmd
python -m pytest tests/ -v
```

---

## Шаг 4. Настройка и индексация

### 4.1. Укажите пути

Скопируйте файл настроек и отредактируйте его:

```cmd
copy .env.example .env
notepad .env
```

**LITE** — без локальной LLM:

```ini
INDEX_FOLDERS=C:\git\MyProject;C:\git\wiki
CHROMA_PATH=C:\git\rag_index
COLLECTION_NAME=my_project
```

**FULL** — раскомментируйте `LLM_MODEL`:

```ini
INDEX_FOLDERS=C:\git\MyProject;C:\git\wiki
CHROMA_PATH=C:\git\rag_index
COLLECTION_NAME=my_project
LLM_MODEL=qwen2.5:3b
```

### 4.2. Запустите индексацию

```cmd
python index_my_project.py
```

Пример вывода:

```
Создаю VectorStore...

Индексирую: C:\git\MyProject (с нуля)
  Загружено файлов: 347
  Создано чанков:   1420
  Всего в индексе:  1420

Индексирую: C:\git\wiki (добавляю)
  Загружено файлов: 89
  Создано чанков:   310
  Всего в индексе:  1730

Готово! Индекс сохранён в: C:\git\rag_index
```

> **Время индексации** зависит от объёма: 500 файлов ~ 2-5 минут.
> **Переиндексация:** запустите скрипт заново — индекс пересоздастся с нуля.

---

## Шаг 5. Подключение к Claude Code (VS Code)

### 5.1. Установите Claude Code

Если ещё не установлен:

```cmd
npm install -g @anthropic-ai/claude-code
```

> Нужен Node.js. Скачать: https://nodejs.org/

### 5.2. Добавьте MCP-сервер

**LITE**:

```cmd
claude mcp add rag-knowledge-base ^
  -e CHROMA_PATH=C:\git\rag_index ^
  -e COLLECTION_NAME=my_project ^
  -- python C:\git\OtusAiForDevs\RAG\server.py
```

**FULL**:

```cmd
claude mcp add rag-knowledge-base ^
  -e CHROMA_PATH=C:\git\rag_index ^
  -e COLLECTION_NAME=my_project ^
  -e LLM_MODEL=qwen2.5:3b ^
  -- python C:\git\OtusAiForDevs\RAG\server.py
```

> Настройки сохраняются в `~/.claude/settings.json` — сервер будет доступен во всех проектах.

### 5.3. Проверьте подключение

Откройте VS Code, запустите Claude Code и напишите:

```
Покажи статус индекса
```

Ожидаемый ответ:

```
Статус индекса:
- Коллекция: my_project
- Чанков в индексе: 1730
- Путь к базе: C:\git\rag_index
```

---

## Шаг 6. Использование

### Доступные инструменты

| Инструмент | Что делает | LITE | FULL |
|---|---|---|---|
| `find_relevant_docs` | Поиск документов по смыслу | ✓ | ✓ |
| `index_folder` | Индексация новой папки | ✓ | ✓ |
| `index_status` | Статус индекса | ✓ | ✓ |
| `ask_question` | Полный Corrective RAG пайплайн | ✗ | ✓ |
| `summarize_document` | Суммаризация файла | ✗ | ✓ |

> **LITE:** `ask_question` и `summarize_document` требуют локальную LLM и не будут работать.
> Но Claude в VS Code делает то же самое — и лучше.

### Примеры запросов

**Найти информацию (LITE и FULL):**

```
Найди в нашей документации всё про авторизацию и объясни, как она работает
```

```
Найди документы про деплой и расскажи процесс развёртывания
```

```
Найди в вики всё, что нужно знать новому разработчику для старта
```

**Задать вопрос напрямую (FULL):**

```
Как у нас реализована авторизация?
```

**Суммаризация файла (FULL):**

```
Сделай краткое содержание файла C:\git\wiki\architecture.md
```

**Переиндексация из чата:**

```
Проиндексируй папку C:\git\wiki с нуля
```

### Как это работает

**LITE** — Claude делает всё сам:

```
Ваш вопрос
    │
    ▼
Claude (мощная модель)
    │
    ├─ вызывает find_relevant_docs
    │       │
    │       ▼
    │  ChromaDB ищет похожие фрагменты
    │  (эмбеддинги от nomic-embed-text)
    │
    ▼
Claude читает фрагменты и генерирует ответ
```

**FULL** — Corrective RAG пайплайн:

```
Ваш вопрос
    │
    ▼
[1] LLM переписывает запрос для лучшего поиска
    │
    ▼
[2] Гибридный поиск в ChromaDB (10 чанков)
    │
    ▼
[3] LLM оценивает релевантность каждого чанка
    │
    ├─ нет релевантных → переформулировать (до 2 попыток)
    │
    ▼
[4] LLM генерирует ответ на основе найденных чанков
    │
    ▼
[5] LLM проверяет: ответ основан на контексте?
    │
    ├─ нет → переформулировать
    │
    ▼
Ответ + список источников
```

---

## Советы

### Большой репозиторий — что индексировать?

Если в моно-репозитории 10 000+ файлов, индексируйте только нужные папки:

```ini
INDEX_FOLDERS=C:\git\MyProject\docs;C:\git\MyProject\src\backend;C:\git\wiki
```

### Какие файлы индексируются?

Все текстовые: `.md`, `.txt`, `.py`, `.cs`, `.js`, `.ts`, `.java`, `.go`, `.yaml`, `.json`, `.xml`, `.html`, `.css` и т.д.

Бинарные файлы (картинки, `.dll`, `.exe`) пропускаются автоматически.

### Как обновить индекс после `git pull`?

Запустите `python index_my_project.py` заново — индекс пересоздастся с нуля.

### Медленная генерация (FULL)?

| Проблема | Решение |
|----------|---------|
| Ответ генерируется 30+ секунд | Нормально для CPU. С GPU NVIDIA — 2-5 секунд |
| Хочу быстрее | `ollama pull qwen2.5:1.5b` и `LLM_MODEL=qwen2.5:1.5b` |

---

## Устранение проблем

### `ModuleNotFoundError: No module named 'chromadb'`

Не активировано виртуальное окружение:

```cmd
cd C:\git\OtusAiForDevs\RAG
venv\Scripts\activate
```

### `ConnectionError: ... localhost:11434`

Ollama не запущена. Запустите приложение (иконка в трее) или:

```cmd
ollama serve
```

### `Python 3.14 ... ConfigError`

ChromaDB не поддерживает Python 3.14. Пересоздайте venv на 3.12:

```cmd
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Claude Code не видит MCP-сервер

```cmd
claude mcp list
```

Если `rag-knowledge-base` нет в списке — добавьте заново (Шаг 5.2).

### Файлы с кириллицей в пути не индексируются

Скопируйте файлы в папку с ASCII-путём (например, `C:\git\wiki`).

---

## Итого

| Шаг | Что делаем | LITE | FULL |
|-----|-----------|------|------|
| 1 | Python 3.12 | 5 мин | 5 мин |
| 2 | Ollama | 3 мин | 10 мин |
| 3 | Clone + pip install | 5 мин | 5 мин |
| 4 | `index_my_project.py` | 2-10 мин | 2-10 мин |
| 5 | `claude mcp add` | 1 мин | 1 мин |
| **Итого** | | **~20 мин** | **~25 мин** |
