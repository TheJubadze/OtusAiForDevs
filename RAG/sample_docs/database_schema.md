# Схема базы данных TaskFlow

## Auth DB (PostgreSQL)

### Таблица users
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UUID | Первичный ключ |
| email | VARCHAR(255) | Уникальный email |
| password_hash | VARCHAR(255) | bcrypt хеш пароля |
| full_name | VARCHAR(100) | Имя и фамилия |
| role_id | UUID | FK → roles.id |
| is_active | BOOLEAN | Активен ли аккаунт (default: true) |
| created_at | TIMESTAMP | Дата создания |
| last_login | TIMESTAMP | Последний вход |

### Таблица roles
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UUID | Первичный ключ |
| name | VARCHAR(50) | admin / manager / member |
| permissions | JSONB | Массив разрешений |

### Таблица refresh_tokens
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UUID | Первичный ключ |
| user_id | UUID | FK → users.id |
| token | VARCHAR(500) | Refresh token |
| expires_at | TIMESTAMP | Время истечения |
| is_revoked | BOOLEAN | Отозван ли токен |

## Task DB (PostgreSQL)

### Таблица projects
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UUID | Первичный ключ |
| name | VARCHAR(100) | Название проекта |
| description | TEXT | Описание |
| owner_id | UUID | ID владельца (из Auth Service) |
| status | VARCHAR(20) | active / archived |
| created_at | TIMESTAMP | Дата создания |

### Таблица sprints
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UUID | Первичный ключ |
| project_id | UUID | FK → projects.id |
| name | VARCHAR(100) | Название спринта |
| start_date | DATE | Начало спринта |
| end_date | DATE | Конец спринта |
| goal | TEXT | Цель спринта |
| status | VARCHAR(20) | planning / active / completed |

### Таблица tasks
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UUID | Первичный ключ |
| project_id | UUID | FK → projects.id |
| sprint_id | UUID | FK → sprints.id (nullable) |
| title | VARCHAR(200) | Заголовок задачи |
| description | TEXT | Описание (Markdown) |
| status | VARCHAR(20) | todo / in_progress / review / done |
| priority | VARCHAR(10) | low / medium / high / critical |
| assignee_id | UUID | ID исполнителя (nullable) |
| reporter_id | UUID | ID создателя |
| estimate_hours | DECIMAL(5,1) | Оценка в часах |
| due_date | DATE | Дедлайн (nullable) |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |

### Таблица comments
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UUID | Первичный ключ |
| task_id | UUID | FK → tasks.id |
| author_id | UUID | ID автора |
| body | TEXT | Текст комментария (Markdown) |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата редактирования |

### Таблица labels
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UUID | Первичный ключ |
| project_id | UUID | FK → projects.id |
| name | VARCHAR(50) | Название метки |
| color | VARCHAR(7) | HEX цвет (#FF5733) |

### Таблица task_labels (M2M)
| Колонка | Тип | Описание |
|---------|-----|----------|
| task_id | UUID | FK → tasks.id |
| label_id | UUID | FK → labels.id |

## Индексы

- `idx_tasks_project_status` — tasks(project_id, status) для фильтрации задач в проекте
- `idx_tasks_assignee` — tasks(assignee_id) для "мои задачи"
- `idx_tasks_sprint` — tasks(sprint_id) для бэклога спринта
- `idx_comments_task` — comments(task_id) для загрузки комментариев
- `idx_users_email` — users(email) UNIQUE для входа

## Миграции

Используем Alembic для управления миграциями. Файлы миграций хранятся в `services/task-service/alembic/versions/`. Для создания новой миграции:

```bash
cd services/task-service
alembic revision --autogenerate -m "описание изменения"
alembic upgrade head
```
