# Docker Compose: справочник конфигурации

## Файлы

| Файл | Назначение |
|------|-----------|
| `docker-compose.yml` | Основной — для локальной разработки |
| `docker-compose.test.yml` | Запуск тестов в изолированном окружении |
| `docker-compose.override.yml` | Локальные переопределения (не коммитится) |

## Сервисы в docker-compose.yml

### postgres
- Образ: `postgres:15-alpine`
- Порт: 5432
- Создаёт две базы при инициализации: `auth_db` и `task_db`
- Volume: `pgdata` для персистентности
- Healthcheck: `pg_isready -U taskflow`

### mongodb
- Образ: `mongo:7`
- Порт: 27017
- Volume: `mongodata`
- Без аутентификации (только для dev)

### rabbitmq
- Образ: `rabbitmq:3-management`
- Порты: 5672 (AMQP), 15672 (Management UI)
- Default credentials: guest/guest
- Healthcheck: `rabbitmq-diagnostics check_port_connectivity`

### minio
- Образ: `minio/minio:latest`
- Порты: 9000 (API), 9001 (Console)
- Автоматически создаёт bucket `taskflow-files` через init-контейнер
- Default credentials: minioadmin/minioadmin

### auth-service
- Build: `./services/auth-service`
- Порт: 8001
- Depends on: postgres
- Запускает миграции при старте: `alembic upgrade head`

### task-service
- Build: `./services/task-service`
- Порт: 8002
- Depends on: postgres, rabbitmq
- Запускает миграции и seed-данные при старте

### notification-service
- Build: `./services/notification-service`
- Порт: 8004
- Depends on: mongodb, rabbitmq

### file-service
- Build: `./services/file-service`
- Порт: 8003
- Depends on: minio

### frontend
- Build: `./frontend`
- Порт: 3000
- Nginx отдаёт статику и проксирует /api/* на Kong

### kong
- Образ: `kong:3.5`
- Порт: 8000
- Декларативная конфигурация: `gateway/kong.yml`
- Depends on: auth-service, task-service, file-service, notification-service

## Volumes

```yaml
volumes:
  pgdata:        # PostgreSQL данные
  mongodata:     # MongoDB данные
  rabbitmqdata:  # RabbitMQ данные и конфигурация
  miniodata:     # MinIO файлы
```

## Сети

Все сервисы находятся в одной сети `taskflow-net` (bridge driver). Сервисы обращаются друг к другу по имени контейнера (например, `postgres:5432`, `rabbitmq:5672`).

## Полезные команды

```bash
# Запуск всех сервисов
docker compose up -d

# Просмотр статуса
docker compose ps

# Логи конкретного сервиса (follow)
docker compose logs -f task-service

# Пересборка после изменений в коде
docker compose up -d --build task-service

# Полная очистка (включая volumes)
docker compose down -v

# Запуск только инфраструктуры (без приложения)
docker compose up -d postgres mongodb rabbitmq minio
```
