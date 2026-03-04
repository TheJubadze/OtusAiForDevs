# Тестирование в TaskFlow

## Стратегия тестирования

Используем пирамиду тестирования:
- **Unit-тесты** (~70%): бизнес-логика сервисов, валидация, утилиты
- **Integration-тесты** (~20%): API-эндпоинты, взаимодействие с БД
- **E2E-тесты** (~10%): критические пользовательские сценарии

## Python Backend — pytest

### Запуск тестов

```bash
# Все тесты
docker compose exec task-service pytest -v

# С покрытием
docker compose exec task-service pytest --cov=app --cov-report=html

# Конкретный файл
docker compose exec task-service pytest tests/test_task_service.py -v

# Конкретный тест
docker compose exec task-service pytest tests/test_task_service.py::test_create_task -v

# Только unit-тесты (по маркеру)
docker compose exec task-service pytest -m unit -v
```

### Конфигурация (conftest.py)

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.models.base import Base

@pytest.fixture
async def db_session():
    """Создаёт чистую БД для каждого теста."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSession(engine) as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def mock_publish_event(mocker):
    """Мокает публикацию событий в RabbitMQ."""
    return mocker.patch("app.events.publisher.publish_event")
```

### Пример unit-теста

```python
import pytest
from uuid import uuid4
from app.services.task_service import TaskService
from app.schemas.task import TaskCreate

@pytest.mark.unit
async def test_create_task_publishes_event(db_session, mock_publish_event):
    """При создании задачи должно публиковаться событие task.created."""
    service = TaskService(db=db_session)
    project = await create_test_project(db_session)
    
    task_data = TaskCreate(
        project_id=project.id,
        title="Test task",
        priority="medium",
    )
    
    result = await service.create_task(task_data, current_user_id=uuid4())
    
    mock_publish_event.assert_called_once()
    call_args = mock_publish_event.call_args
    assert call_args.kwargs["exchange"] == "task.events"
    assert call_args.kwargs["routing_key"] == "task.created"
    assert call_args.kwargs["body"]["title"] == "Test task"

@pytest.mark.unit
async def test_cannot_start_task_without_assignee(db_session):
    """Задачу нельзя перевести в in_progress без исполнителя."""
    service = TaskService(db=db_session)
    task = await create_test_task(db_session, assignee_id=None)
    
    with pytest.raises(HTTPException) as exc_info:
        await service.update_task_status(
            task_id=task.id,
            new_status=TaskStatus.IN_PROGRESS,
            current_user_id=uuid4(),
        )
    
    assert exc_info.value.status_code == 422
    assert "assignee" in exc_info.value.detail.lower()
```

### Пример integration-теста

```python
import pytest
from httpx import AsyncClient

@pytest.mark.integration
async def test_task_crud_flow(client: AsyncClient, auth_headers):
    """Полный цикл: создание → обновление → удаление задачи через API."""
    # Создание
    response = await client.post(
        "/api/tasks/tasks",
        json={
            "project_id": str(test_project_id),
            "title": "Integration test task",
            "priority": "high",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    task_id = response.json()["id"]
    
    # Обновление
    response = await client.patch(
        f"/api/tasks/tasks/{task_id}",
        json={"title": "Updated title"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"
    
    # Удаление
    response = await client.delete(
        f"/api/tasks/tasks/{task_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204
```

## Frontend — Vitest

### Запуск

```bash
cd frontend
npm run test        # watch mode
npm run test:ci     # single run с покрытием
```

### Пример теста компонента

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { TaskCard } from './TaskCard';

describe('TaskCard', () => {
  it('shows priority badge with correct color', () => {
    render(<TaskCard task={mockTask({ priority: 'critical' })} />);
    const badge = screen.getByText('critical');
    expect(badge).toHaveClass('bg-red-500');
  });

  it('calls onStatusChange when status is updated', async () => {
    const onStatusChange = vi.fn();
    render(<TaskCard task={mockTask()} onStatusChange={onStatusChange} />);
    
    fireEvent.click(screen.getByText('Mark as Done'));
    
    expect(onStatusChange).toHaveBeenCalledWith('done');
  });
});
```

## Минимальные требования покрытия

| Сервис | Покрытие | Критичные модули |
|--------|----------|-----------------|
| Auth Service | ≥80% | auth logic: ≥95% |
| Task Service | ≥80% | task_service.py: ≥90% |
| Frontend | ≥70% | hooks, utils: ≥85% |
