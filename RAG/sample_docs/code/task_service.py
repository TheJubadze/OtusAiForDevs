"""
Task Service — сервис управления задачами.
Основной бизнес-логика: CRUD задач, проектов и спринтов.
"""

from uuid import UUID
from datetime import datetime, date

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.dependencies import get_db, get_current_user
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.project import Project
from app.schemas.task import TaskCreate, TaskUpdate, TaskRead, TaskFilters
from app.schemas.common import PaginationParams, PaginatedResponse
from app.events.publisher import publish_event


class TaskService:
    """Сервис для работы с задачами.
    
    Инкапсулирует бизнес-логику создания, обновления и удаления задач.
    Взаимодействует с TaskRepository для доступа к БД и с RabbitMQ
    для публикации событий.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_tasks(
        self,
        project_id: UUID,
        filters: TaskFilters,
        pagination: PaginationParams,
    ) -> PaginatedResponse[TaskRead]:
        """Получение списка задач с фильтрацией и пагинацией.

        Args:
            project_id: ID проекта.
            filters: Фильтры (status, priority, assignee_id, search).
            pagination: Параметры пагинации.

        Returns:
            Пагинированный ответ со списком задач.
        """
        query = select(Task).where(Task.project_id == project_id)

        if filters.status:
            query = query.where(Task.status == filters.status)
        if filters.priority:
            query = query.where(Task.priority == filters.priority)
        if filters.assignee_id:
            query = query.where(Task.assignee_id == filters.assignee_id)
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.where(
                Task.title.ilike(search_term) | Task.description.ilike(search_term)
            )

        # Подсчёт общего количества
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)

        # Пагинация и сортировка
        query = query.order_by(Task.created_at.desc())
        query = query.offset((pagination.page - 1) * pagination.per_page)
        query = query.limit(pagination.per_page)

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        return PaginatedResponse(
            items=[TaskRead.model_validate(t) for t in tasks],
            total=total,
            page=pagination.page,
            per_page=pagination.per_page,
        )

    async def create_task(
        self,
        data: TaskCreate,
        current_user_id: UUID,
    ) -> TaskRead:
        """Создание новой задачи.

        Args:
            data: Данные для создания задачи.
            current_user_id: ID текущего пользователя (reporter).

        Returns:
            Созданная задача.

        Raises:
            HTTPException(404): Проект не найден.
            HTTPException(422): Дедлайн в прошлом.
        """
        # Проверяем существование проекта
        project = await self.db.get(Project, data.project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {data.project_id} not found",
            )

        # Валидация дедлайна
        if data.due_date and data.due_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Due date cannot be in the past",
            )

        task = Task(
            **data.model_dump(exclude={"label_ids"}),
            reporter_id=current_user_id,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        # Публикуем событие
        await publish_event(
            exchange="task.events",
            routing_key="task.created",
            body={
                "task_id": str(task.id),
                "title": task.title,
                "project_id": str(task.project_id),
                "reporter_id": str(current_user_id),
                "assignee_id": str(task.assignee_id) if task.assignee_id else None,
            },
        )

        return TaskRead.model_validate(task)

    async def update_task_status(
        self,
        task_id: UUID,
        new_status: TaskStatus,
        current_user_id: UUID,
    ) -> TaskRead:
        """Обновление статуса задачи с бизнес-правилами.

        При переходе в 'in_progress' проверяется наличие assignee.
        При переходе в 'done' устанавливается completed_at.

        Args:
            task_id: ID задачи.
            new_status: Новый статус.
            current_user_id: ID пользователя, меняющего статус.

        Returns:
            Обновлённая задача.
        """
        task = await self.db.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        old_status = task.status

        # Бизнес-правило: нельзя начать работу без исполнителя
        if new_status == TaskStatus.IN_PROGRESS and not task.assignee_id:
            raise HTTPException(
                status_code=422,
                detail="Cannot move to 'in_progress' without assignee",
            )

        # Установка/сброс completed_at
        if new_status == TaskStatus.DONE:
            task.completed_at = datetime.utcnow()
        elif old_status == TaskStatus.DONE:
            task.completed_at = None

        task.status = new_status
        task.updated_at = datetime.utcnow()
        await self.db.commit()

        # Публикуем событие о смене статуса
        await publish_event(
            exchange="task.events",
            routing_key="task.status_changed",
            body={
                "task_id": str(task.id),
                "old_status": old_status.value,
                "new_status": new_status.value,
                "changed_by": str(current_user_id),
            },
        )

        return TaskRead.model_validate(task)

    async def get_project_stats(self, project_id: UUID) -> dict:
        """Статистика проекта для дашборда.

        Args:
            project_id: ID проекта.

        Returns:
            Словарь со статистикой: задачи по статусам, приоритетам,
            количество просроченных, процент выполнения.
        """
        # Задачи по статусам
        status_query = (
            select(Task.status, func.count())
            .where(Task.project_id == project_id)
            .group_by(Task.status)
        )
        status_result = await self.db.execute(status_query)
        by_status = dict(status_result.all())

        # Просроченные задачи
        overdue_query = (
            select(func.count())
            .where(
                and_(
                    Task.project_id == project_id,
                    Task.due_date < date.today(),
                    Task.status != TaskStatus.DONE,
                )
            )
        )
        overdue_count = await self.db.scalar(overdue_query)

        total = sum(by_status.values())
        done = by_status.get(TaskStatus.DONE, 0)

        return {
            "total_tasks": total,
            "by_status": by_status,
            "overdue_tasks": overdue_count,
            "completion_rate": round(done / total * 100, 1) if total > 0 else 0,
        }
```
