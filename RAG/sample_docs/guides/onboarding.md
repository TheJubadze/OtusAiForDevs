# Onboarding: Как начать работу новому разработчику

## Необходимые инструменты

Перед началом работы убедитесь, что установлены:
- **Docker Desktop** (v24+) — для запуска всех сервисов
- **Python 3.11+** — для backend-сервисов
- **Node.js 20 LTS** — для Notification Service и фронтенда
- **Git** — для работы с репозиториями
- **VS Code** (рекомендуется) с расширениями: Python, ESLint, Prettier, Docker

## Клонирование и запуск

```bash
# 1. Клонируйте монорепо
git clone https://dev.azure.com/taskflow/taskflow/_git/taskflow-mono
cd taskflow-mono

# 2. Скопируйте файл с переменными окружения
cp .env.example .env

# 3. Запустите всё через Docker Compose
docker compose up -d

# 4. Подождите ~2 минуты, пока скачаются образы и стартуют сервисы
docker compose ps   # все сервисы должны быть в статусе "running"
```

## Доступные сервисы после запуска

| Сервис | URL | Описание |
|--------|-----|----------|
| Frontend | http://localhost:3000 | React SPA |
| API Gateway | http://localhost:8000 | Kong |
| Auth Service | http://localhost:8001 | Swagger: /docs |
| Task Service | http://localhost:8002 | Swagger: /docs |
| File Service | http://localhost:8003 | Swagger: /docs |
| RabbitMQ UI | http://localhost:15672 | guest/guest |
| Grafana | http://localhost:3001 | admin/admin |
| pgAdmin | http://localhost:5050 | admin@taskflow.dev / admin |

## Тестовые учётные записи

| Email | Пароль | Роль |
|-------|--------|------|
| admin@taskflow.dev | Admin123! | admin |
| ivan@taskflow.dev | Ivan123! | manager |
| maria@taskflow.dev | Maria123! | member |

## Структура монорепо

```
taskflow-mono/
├── services/
│   ├── auth-service/        # Python, FastAPI
│   ├── task-service/        # Python, FastAPI
│   ├── notification-service/ # Node.js, Express
│   └── file-service/        # Python, FastAPI
├── frontend/                # React + TypeScript
├── gateway/                 # Kong конфигурация
├── docker-compose.yml
├── docker-compose.test.yml
├── .env.example
└── docs/                    # Документация (вы здесь)
```

## Типичный рабочий процесс

1. Создайте ветку от `develop`: `git checkout -b feature/TASK-123-описание`
2. Вносите изменения, пишите тесты
3. Запустите тесты локально: `docker compose -f docker-compose.test.yml up --abort-on-container-exit`
4. Создайте Pull Request в `develop`
5. Дождитесь code review (минимум 1 approve) и прохождения CI
6. Merge через Squash strategy

## Если что-то не работает

1. **Порты заняты**: остановите другие Docker-контейнеры (`docker stop $(docker ps -q)`)
2. **Миграции не прошли**: `docker compose exec task-service alembic upgrade head`
3. **Фронтенд не видит API**: проверьте, что Kong запустился (`curl http://localhost:8000/api/health`)
4. **Нет seed-данных**: `docker compose exec task-service python scripts/seed.py`

## Полезные команды

```bash
# Логи конкретного сервиса
docker compose logs -f task-service

# Зайти в контейнер
docker compose exec task-service bash

# Пересобрать один сервис после изменений
docker compose up -d --build task-service

# Запустить тесты одного сервиса
docker compose exec task-service pytest -v

# Применить миграции
docker compose exec task-service alembic upgrade head

# Сбросить БД и накатить seed-данные
docker compose exec task-service python scripts/reset_db.py
```
