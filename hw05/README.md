# MCP Video Library Server

MCP-сервер для управления локальной видеотекой с интеграцией внешних API (TMDb, OMDb, Kinopoisk).

## Оглавление
- [Принципы работы MCP](#принципы-работы-mcp)
- [Установка и запуск](#установка-и-запуск)
- [Инструменты (Tools)](#инструменты-tools)
- [Интеграция с IDE](#интеграция-с-ide)
- [Логирование](#логирование)
- [Проверочные запросы](#проверочные-запросы)
- [Ссылки на код](#ссылки-на-код)
- [Контракт результатов Tool](#контракт-результатов-tool)

---

## Принципы работы MCP

### Как IDE/агент подключается к MCP-серверу

MCP (Model Context Protocol) — это протокол, позволяющий AI-агентам (например, Claude) взаимодействовать с внешними инструментами. В данном проекте используется транспорт **stdio** (стандартный ввод/вывод): IDE запускает Python-скрипт сервера как дочерний процесс и обменивается с ним JSON-RPC сообщениями через stdin/stdout. При запуске сервер регистрирует доступные инструменты через декоратор `@server.list_tools()`, и агент получает их список при инициализации соединения. Когда пользователь в IDE-чате задаёт вопрос, требующий данных из видеотеки, агент автоматически вызывает нужный инструмент через `@server.call_tool()`.

### Что является «tool» в этом сервере

«Tool» (инструмент) — это функция с чётко определённой схемой входных параметров и структурированным JSON-ответом, которую AI-агент может вызывать для получения данных или выполнения действий. В данном сервере реализовано **8 инструментов**: от простого получения списка файлов (`list_movies`, `list_cartoons`) до сложных операций с внешними API (`get_movie_info`, `rename_movie`) и анализа метаданных видео (`get_video_metadata`). Каждый инструмент имеет описание на естественном языке, JSON-схему параметров и возвращает структурированный результат.

---

## Установка и запуск

### Требования
- Python 3.10+
- FFmpeg (для инструмента `get_video_metadata`)
- API-ключи: TMDb, OMDb (опционально: Kinopoisk)

### Шаги установки

1. **Клонируйте репозиторий и перейдите в папку проекта:**
   ```bash
   cd mcp-videolibrary
   ```

2. **Создайте виртуальное окружение и установите зависимости:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   pip install tmdbsimple googlesearch-python beautifulsoup4
   ```

3. **Создайте файл конфигурации:**
   ```bash
   cp config.json.example config.json
   ```
   Отредактируйте `config.json`, указав:
   - Путь к папкам с видео (`videos_root`, `movies_folder`, `cartoons_folder`)
   - API-ключи (`tmdb_api_key`, `kinopoisk_api_key`)

4. **Установите переменную окружения для OMDb:**
   ```bash
   set OMDB_API_KEY=ваш_ключ  # Windows
   ```

5. **Проверьте запуск сервера:**
   ```bash
   python server.py
   ```
   В логах должно появиться: `🚀 MCP СЕРВЕР 'videolibrary' ЗАПУЩЕН`

---

## Инструменты (Tools)

| Инструмент | Описание | Параметры |
|------------|----------|-----------|
| `list_movies` | Список всех фильмов в библиотеке | `limit` (опц.) |
| `list_cartoons` | Список всех мультфильмов | `limit` (опц.) |
| `get_movie_info` | Информация о фильме из TMDb/OMDb | `title` (обяз.), `year` (опц.) |
| `search_library` | Поиск по названию в библиотеке | `query` (обяз.), `category` (опц.) |
| `get_library_stats` | Статистика библиотеки | — |
| `get_movie_info_by_file` | Информация по имени файла | `filename` (обяз.) |
| `rename_movie` | Переименование в формат "Название (Год) - Режиссёр" | `filepath` (обяз.), `dry_run` (опц.) |
| `get_video_metadata` | Технические метаданные (FFprobe) | `filepath` (обяз.) |

---

## Интеграция с IDE

### Конфигурация для Claude Code (VSCode)

Создайте или отредактируйте файл `.claude/settings.local.json` в корне проекта:

```json
{
  "mcpServers": {
    "videolibrary": {
      "command": "python",
      "args": ["d:/Dev/OtusAiForDevs/hw05/mcp-videolibrary/server.py"],
      "env": {
        "OMDB_API_KEY": "ваш_omdb_ключ"
      }
    }
  },
  "permissions": {
    "allow": [
      "mcp__videolibrary__list_movies",
      "mcp__videolibrary__list_cartoons",
      "mcp__videolibrary__get_movie_info",
      "mcp__videolibrary__search_library",
      "mcp__videolibrary__get_library_stats",
      "mcp__videolibrary__get_movie_info_by_file",
      "mcp__videolibrary__rename_movie",
      "mcp__videolibrary__get_video_metadata"
    ]
  }
}
```

### Как включить (5 шагов)

1. Скопируйте конфигурацию выше в `.claude/settings.local.json`
2. Укажите корректный путь к `server.py` в поле `args`
3. Добавьте API-ключи в секцию `env`
4. Перезапустите Claude Code (VSCode)
5. В чате агента спросите: "Покажи статистику видеотеки" — должен вызваться `get_library_stats`

---

## Логирование

### Где хранятся логи

Файл логов: `mcp-videolibrary/mcp_server.log` (исключён из git через `.gitignore`)

### Формат логов

Каждый вызов инструмента логируется в структурированном формате:

```
====================================================================================================
🤖 ВХОДЯЩИЙ ЗАПРОС ОТ AI АГЕНТА (CLAUDE)
====================================================================================================
📥 Инструмент: <имя_инструмента>
📋 Аргументы:
   • param1: value1
   • param2: value2
----------------------------------------------------------------------------------------------------
⚙️  Обработка:
   <детали выполнения: сканирование папок, API-запросы, FFprobe>
----------------------------------------------------------------------------------------------------
📤 ОТВЕТ (⏱  X.XXс)
====================================================================================================
📦 Результат [1]:
   { JSON-ответ }
====================================================================================================
```

### Реализация логирования

См. [server.py:33-43](mcp-videolibrary/server.py#L33-L43) — настройка логгера
См. [server.py:902-928](mcp-videolibrary/server.py#L902-L928) — функция `log_response()`
См. [server.py:931-946](mcp-videolibrary/server.py#L931-L946) — логирование входящего запроса

---

## Проверочные запросы

### Запрос 1: Статистика библиотеки
**Запрос пользователя:** "Покажи статистику моей видеотеки"
**Ожидаемый tool:** `get_library_stats`
**Подтверждение из лога:**
```
2026-02-02 23:11:32,224 - INFO - 📥 Инструмент: get_library_stats
2026-02-02 23:11:32,224 - INFO - 📋 Аргументы:
```

### Запрос 2: Список фильмов
**Запрос пользователя:** "Покажи первые 5 фильмов"
**Ожидаемый tool:** `list_movies`
**Подтверждение из лога:**
```
2026-02-02 20:52:40,093 - INFO - 📥 Инструмент: list_movies
2026-02-02 20:52:40,093 - INFO - 📋 Аргументы:
   • limit: 0
```

### Запрос 3: Переименование фильма
**Запрос пользователя:** "Переименуй фильм Gravity в правильный формат"
**Ожидаемый tool:** `rename_movie`
**Подтверждение из лога:**
```
2026-02-02 20:53:22,498 - INFO - 📥 Инструмент: rename_movie
2026-02-02 20:53:22,498 - INFO - 📋 Аргументы:
   • filepath: T:\Movies\Gravity [BDRip-720p 60 FPS] By EXCLUSIF.mkv
   • dry_run: False
...
2026-02-02 20:53:22,491 - INFO - "new_file": "Гравитация (2013) - Alfonso Cuarón.mkv"
2026-02-02 20:53:22,491 - INFO - "status": "success"
```

### Запрос 4: Технические метаданные видео
**Запрос пользователя:** "Покажи технические характеристики мультфильма Рио 2"
**Ожидаемый tool:** `get_video_metadata`
**Подтверждение из лога:**
```
2026-02-03 13:31:34,034 - INFO - 📥 Инструмент: get_video_metadata
2026-02-03 13:31:34,034 - INFO - 📋 Аргументы:
   • filepath: T:\Cartoons\Рио 2 (2014).mkv
...
2026-02-03 13:31:34,178 - INFO - ✅ 1920x800 | h264 | 1:41:11 | HD (720p)
```

### Запрос 5: Информация о фильме по файлу
**Запрос пользователя:** "Найди информацию о фильме Geralds.Game.2017.1080p.NF.WEBRip"
**Ожидаемый tool:** `get_movie_info_by_file` или `rename_movie`
**Подтверждение из лога:**
```
2026-02-02 20:53:15,754 - INFO - 📥 Инструмент: rename_movie
2026-02-02 20:53:15,754 - INFO - 📋 Аргументы:
   • filepath: T:\Movies\Geralds.Game.2017.1080p.NF.WEBRip.DD5.1.x264.RUS.MVO-NTb.mkv
...
2026-02-02 20:53:20,079 - INFO - "title": "Игра Джералда"
2026-02-02 20:53:20,079 - INFO - "year": "2017"
2026-02-02 20:53:20,079 - INFO - "director": "Mike Flanagan"
```

---

## Ссылки на код

### Реализация MCP-сервера
- **Инициализация сервера и импорты:** [server.py:1-27](mcp-videolibrary/server.py#L1-L27)
- **Настройка логирования:** [server.py:33-43](mcp-videolibrary/server.py#L33-L43)
- **Создание экземпляра Server:** [server.py:86](mcp-videolibrary/server.py#L86)
- **Регистрация инструментов (`@server.list_tools`):** [server.py:774-899](mcp-videolibrary/server.py#L774-L899)
- **Диспетчер вызовов (`@server.call_tool`):** [server.py:931-1160](mcp-videolibrary/server.py#L931-L1160)
- **Точка входа и запуск stdio_server:** [server.py:1163-1187](mcp-videolibrary/server.py#L1163-L1187)

### Реализация инструментов

| Инструмент | Регистрация (схема) | Реализация (логика) | Логирование |
|------------|---------------------|---------------------|-------------|
| `list_movies` | [server.py:778-791](mcp-videolibrary/server.py#L778-L791) | [server.py:951-963](mcp-videolibrary/server.py#L951-L963) | [server.py:954,958](mcp-videolibrary/server.py#L954) |
| `list_cartoons` | [server.py:792-805](mcp-videolibrary/server.py#L792-L805) | [server.py:965-977](mcp-videolibrary/server.py#L965-L977) | [server.py:968,972](mcp-videolibrary/server.py#L968) |
| `get_movie_info` | [server.py:806-823](mcp-videolibrary/server.py#L806-L823) | [server.py:979-984](mcp-videolibrary/server.py#L979-L984) | [server.py:394-440](mcp-videolibrary/server.py#L394-L440) |
| `search_library` | [server.py:824-843](mcp-videolibrary/server.py#L824-L843) | [server.py:986-1008](mcp-videolibrary/server.py#L986-L1008) | [server.py:989,1003](mcp-videolibrary/server.py#L989) |
| `get_library_stats` | [server.py:844-851](mcp-videolibrary/server.py#L844-L851) | [server.py:1010-1047](mcp-videolibrary/server.py#L1010-L1047) | [server.py:1029-1030](mcp-videolibrary/server.py#L1029-L1030) |
| `get_movie_info_by_file` | [server.py:852-865](mcp-videolibrary/server.py#L852-L865) | [server.py:1049-1063](mcp-videolibrary/server.py#L1049-L1063) | [server.py:1055](mcp-videolibrary/server.py#L1055) |
| `rename_movie` | [server.py:866-884](mcp-videolibrary/server.py#L866-L884) | [server.py:1065-1131](mcp-videolibrary/server.py#L1065-L1131) | [server.py:1079-1080,1103,1120,1125,1129](mcp-videolibrary/server.py#L1079) |
| `get_video_metadata` | [server.py:885-898](mcp-videolibrary/server.py#L885-L898) | [server.py:1133-1153](mcp-videolibrary/server.py#L1133-L1153) | [server.py:1143,1149,1151](mcp-videolibrary/server.py#L1143) |

### Вспомогательные функции
- **Сканирование папки:** [server.py:236-263](mcp-videolibrary/server.py#L236-L263)
- **Очистка имени файла:** [server.py:150-223](mcp-videolibrary/server.py#L150-L223)
- **Запрос к TMDb API:** [server.py:443-557](mcp-videolibrary/server.py#L443-L557)
- **Запрос к Kinopoisk API:** [server.py:625-771](mcp-videolibrary/server.py#L625-L771)
- **FFprobe метаданные:** [server.py:266-389](mcp-videolibrary/server.py#L266-L389)

---

## Контракт результатов Tool

Все инструменты возвращают JSON-объект. Ниже описаны структуры ответов:

### list_movies / list_cartoons
```json
{
  "count": 174,
  "movies": [
    {
      "name": "Film Name.mkv",
      "path": "T:\\Movies\\Film Name.mkv",
      "size_mb": 4388.39,
      "extension": ".mkv",
      "folder": "movies"
    }
  ]
}
```

### get_movie_info / get_movie_info_by_file
```json
{
  "title": "Название фильма",
  "year": "2023",
  "rated": "PG-13",
  "released": "2023-05-15",
  "runtime": "120 min",
  "genre": "Action, Drama",
  "director": "Director Name",
  "actors": "Actor 1, Actor 2",
  "plot": "Описание сюжета...",
  "language": "en",
  "country": "США",
  "poster": "https://image.tmdb.org/...",
  "imdb_rating": "7.5",
  "imdb_id": "tt1234567",
  "type": "movie",
  "box_office": "$100,000,000"
}
```

### search_library
```json
{
  "query": "matrix",
  "count": 3,
  "results": [
    {
      "name": "Matrix.mkv",
      "path": "T:\\Movies\\Matrix.mkv",
      "size_mb": 5000.0,
      "extension": ".mkv",
      "folder": "movies"
    }
  ]
}
```

### get_library_stats
```json
{
  "movies": {
    "count": 174,
    "total_size_gb": 850.5,
    "formats": {".mkv": 150, ".mp4": 24}
  },
  "cartoons": {
    "count": 45,
    "total_size_gb": 200.3,
    "formats": {".mkv": 45}
  },
  "total": {
    "count": 219,
    "total_size_gb": 1050.8
  }
}
```

### rename_movie
```json
{
  "original_file": "Gravity [BDRip-720p].mkv",
  "new_file": "Гравитация (2013) - Alfonso Cuarón.mkv",
  "original_path": "T:\\Movies\\Gravity [BDRip-720p].mkv",
  "new_path": "T:\\Movies\\Гравитация (2013) - Alfonso Cuarón.mkv",
  "movie_info": {
    "title": "Гравитация",
    "year": "2013",
    "director": "Alfonso Cuarón"
  },
  "dry_run": false,
  "status": "success"
}
```

### get_video_metadata
```json
{
  "filename": "Film.mkv",
  "filepath": "T:\\Movies\\Film.mkv",
  "format": {
    "container": "Matroska / WebM",
    "duration": "1:41:11",
    "duration_seconds": 6071.23,
    "size_mb": 10702.06,
    "bitrate_kbps": 14787
  },
  "video": {
    "codec": "H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10",
    "codec_short": "h264",
    "resolution": "1920x800",
    "width": 1920,
    "height": 800,
    "quality": "Full HD (1080p)",
    "fps": 23.98,
    "pixel_format": "yuv420p",
    "hdr": "SDR"
  },
  "audio": [
    {
      "codec": "DTS",
      "codec_short": "dts",
      "channels": "5.1",
      "sample_rate": "48 kHz",
      "bitrate_kbps": 1536,
      "language": "rus"
    }
  ]
}
```

---

## Безопасность

### Ограничения доступа
- **Файловые операции** ограничены папками, указанными в `config.json` (`videos_root`)
- **Команда `rename_movie`** переименовывает файлы только внутри этих папок
- **FFprobe** запускается только для файлов с видео-расширениями

### Секреты
- API-ключи хранятся в `config.json` (исключён из git) или переменных окружения
- Файл `.env` и `.claude/` добавлены в `.gitignore`
- Пример конфигурации без секретов: [config.json.example](mcp-videolibrary/config.json.example)

---

## Файлы проекта

```
hw05/
├── .claude/
│   └── settings.local.json    # Конфигурация MCP для Claude Code (не в git)
├── .gitignore                 # Исключения для git
├── README.md                  # Этот файл
└── mcp-videolibrary/
    ├── server.py              # Основной MCP-сервер (1187 строк)
    ├── config.json.example    # Пример конфигурации
    ├── requirements.txt       # Python-зависимости
    └── mcp_server.log         # Логи сервера (не в git)
```
