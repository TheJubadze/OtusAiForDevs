# API Reference — Task Service

Base URL: `http://localhost:8000/api/tasks`

Все эндпоинты требуют заголовок `Authorization: Bearer <access_token>`, если не указано иное.

## Задачи (Tasks)

### GET /tasks
Список задач с фильтрацией и пагинацией.

**Query параметры:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| project_id | UUID | Фильтр по проекту (обязательный) |
| sprint_id | UUID | Фильтр по спринту |
| status | string | todo / in_progress / review / done |
| priority | string | low / medium / high / critical |
| assignee_id | UUID | Фильтр по исполнителю |
| search | string | Полнотекстовый поиск по title и description |
| page | int | Номер страницы (default: 1) |
| per_page | int | Элементов на странице (default: 20, max: 100) |
| sort_by | string | created_at / updated_at / priority / due_date |
| sort_order | string | asc / desc (default: desc) |

**Ответ (200):**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Реализовать фильтрацию задач",
      "status": "in_progress",
      "priority": "high",
      "assignee": {
        "id": "...",
        "full_name": "Иван Петров"
      },
      "due_date": "2024-02-15",
      "labels": [
        {"id": "...", "name": "backend", "color": "#3B82F6"}
      ],
      "comments_count": 3,
      "created_at": "2024-01-20T10:30:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "per_page": 20
}
```

### POST /tasks
Создание задачи.

**Body (JSON):**
```json
{
  "project_id": "UUID",
  "sprint_id": "UUID (optional)",
  "title": "string (3-200 символов)",
  "description": "string (optional, Markdown)",
  "priority": "low | medium | high | critical",
  "assignee_id": "UUID (optional)",
  "estimate_hours": 4.5,
  "due_date": "2024-02-15",
  "label_ids": ["UUID", "UUID"]
}
```

**Валидация:**
- title: обязательное, 3–200 символов
- priority: обязательное, одно из допустимых значений
- estimate_hours: 0.5–999.9
- due_date: не может быть в прошлом
- assignee_id: должен быть участником проекта

**Ответ (201):** Созданная задача с полными данными.

**Побочные эффекты:**
- Событие `task.created` публикуется в RabbitMQ
- Если указан assignee — уведомление о назначении

### PATCH /tasks/{task_id}
Частичное обновление задачи.

**Body (JSON):** Любые поля из POST (все опциональные).

**Специальное поведение при смене статуса:**
- `todo` → `in_progress`: проверяется наличие assignee
- `* → done`: устанавливается completed_at
- `done → *`: completed_at обнуляется
- Событие `task.status_changed` публикуется с old_status и new_status

### DELETE /tasks/{task_id}
Удаление задачи. Требует роль admin или manager, либо быть reporter задачи.

**Ответ (204):** No content.

### GET /tasks/{task_id}
Получение задачи с полными данными, включая комментарии.

## Комментарии (Comments)

### GET /tasks/{task_id}/comments
Список комментариев к задаче. Пагинация: page, per_page.

### POST /tasks/{task_id}/comments
Добавление комментария.

**Body:**
```json
{
  "body": "string (1-5000 символов, Markdown)"
}
```

**Побочные эффекты:**
- Уведомление assignee и reporter задачи (если комментатор — другой человек)

## Проекты (Projects)

### GET /projects
Список проектов, доступных текущему пользователю.

### POST /projects
Создание проекта. Требует роль admin или manager.

```json
{
  "name": "string (3-100 символов)",
  "description": "string (optional)"
}
```

### GET /projects/{project_id}/stats
Статистика проекта для дашборда.

**Ответ:**
```json
{
  "total_tasks": 42,
  "by_status": {
    "todo": 10,
    "in_progress": 15,
    "review": 7,
    "done": 10
  },
  "by_priority": {
    "low": 5,
    "medium": 20,
    "high": 12,
    "critical": 5
  },
  "overdue_tasks": 3,
  "completion_rate": 23.8,
  "avg_completion_time_hours": 18.5
}
```

## Коды ошибок

| Код | Описание |
|-----|----------|
| 400 | Невалидные данные (детали в body.errors) |
| 401 | Отсутствует или невалидный JWT |
| 403 | Недостаточно прав для операции |
| 404 | Ресурс не найден |
| 409 | Конфликт (например, дублирование имени проекта) |
| 422 | Бизнес-ошибка (например, спринт уже завершён) |
| 429 | Превышен rate limit |
