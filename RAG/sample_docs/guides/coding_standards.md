# Стандарты кодирования TaskFlow

## Python (Backend Services)

### Стиль кода
- Следуем PEP 8 с максимальной длиной строки 100 символов
- Используем **black** для автоформатирования, **ruff** для линтинга
- Type hints обязательны для всех публичных функций и методов
- Docstrings в формате Google Style для всех публичных функций

### Пример оформления функции

```python
async def get_tasks(
    project_id: UUID,
    filters: TaskFilters,
    pagination: PaginationParams,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TaskRead]:
    """Получение списка задач проекта с фильтрацией.

    Args:
        project_id: Идентификатор проекта.
        filters: Параметры фильтрации (status, priority, assignee_id).
        pagination: Параметры пагинации (page, per_page).
        db: Сессия базы данных.

    Returns:
        Пагинированный список задач.

    Raises:
        ProjectNotFoundError: Если проект не существует.
        PermissionDeniedError: Если пользователь не имеет доступа к проекту.
    """
    ...
```

### Структура сервиса

Каждый Python-сервис организован по слоям:

```
service-name/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app, middleware, startup/shutdown
│   ├── config.py          # Pydantic Settings
│   ├── dependencies.py    # Общие зависимости (get_db, get_current_user)
│   ├── models/            # SQLAlchemy модели
│   │   ├── __init__.py
│   │   └── task.py
│   ├── schemas/           # Pydantic схемы (request/response)
│   │   ├── __init__.py
│   │   └── task.py
│   ├── routers/           # FastAPI роутеры
│   │   ├── __init__.py
│   │   └── tasks.py
│   ├── services/          # Бизнес-логика
│   │   ├── __init__.py
│   │   └── task_service.py
│   └── repositories/      # Работа с БД
│       ├── __init__.py
│       └── task_repository.py
├── alembic/               # Миграции
├── tests/
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

### Обработка ошибок

Используем кастомные исключения, которые перехватываются middleware:

```python
class TaskFlowError(Exception):
    def __init__(self, message: str, code: str, status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code

class NotFoundError(TaskFlowError):
    def __init__(self, entity: str, entity_id: UUID):
        super().__init__(
            message=f"{entity} with id {entity_id} not found",
            code="NOT_FOUND",
            status_code=404,
        )
```

## TypeScript (Frontend)

### Стиль кода
- ESLint + Prettier с конфигурацией из корня монорепо
- Functional components с hooks (никаких class components)
- CSS: Tailwind CSS, никаких inline styles или CSS modules

### Именование
- Компоненты: PascalCase (TaskCard.tsx)
- Хуки: camelCase с префиксом use (useTaskFilters.ts)
- Утилиты: camelCase (formatDate.ts)
- Типы и интерфейсы: PascalCase с суффиксом (TaskCreateRequest, TaskListResponse)

### Структура фронтенда

```
frontend/src/
├── components/       # Переиспользуемые UI-компоненты
│   ├── ui/           # Базовые (Button, Input, Modal)
│   └── shared/       # Общие (UserAvatar, StatusBadge)
├── features/         # Фичи (feature-sliced)
│   ├── tasks/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── api/
│   │   └── types/
│   └── projects/
├── pages/            # Страницы (react-router)
├── hooks/            # Глобальные хуки
├── api/              # API-клиент, interceptors
├── store/            # Zustand stores
└── utils/            # Утилиты
```

## Git Conventions

### Формат коммитов
Следуем Conventional Commits:

```
feat(tasks): add priority filter to task list
fix(auth): handle expired refresh token correctly
docs(api): update task API reference
refactor(task-service): extract validation to separate module
test(tasks): add integration tests for task creation
chore(ci): update Node.js version in pipeline
```

### Ветвление
- `main` — production, деплой автоматический
- `develop` — интеграционная ветка
- `feature/TASK-XXX-description` — фичи
- `fix/TASK-XXX-description` — баг-фиксы
- `hotfix/description` — срочные фиксы в production
