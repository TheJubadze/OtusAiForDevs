# Переменные окружения (.env)

Шаблон: `.env.example`. Скопируйте в `.env` и заполните.

## Базы данных

```bash
# PostgreSQL для Auth Service
AUTH_DB_HOST=postgres
AUTH_DB_PORT=5432
AUTH_DB_NAME=auth_db
AUTH_DB_USER=taskflow
AUTH_DB_PASSWORD=taskflow_secret

# PostgreSQL для Task Service
TASK_DB_HOST=postgres
TASK_DB_PORT=5432
TASK_DB_NAME=task_db
TASK_DB_USER=taskflow
TASK_DB_PASSWORD=taskflow_secret

# MongoDB для Notification Service
MONGODB_URL=mongodb://mongodb:27017/notifications
```

## Аутентификация

```bash
# JWT ключи (RS256)
# Для генерации: openssl genrsa -out jwt_private.pem 2048
#                openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
JWT_PRIVATE_KEY_PATH=/app/keys/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/app/keys/jwt_public.pem
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

## RabbitMQ

```bash
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VHOST=/
```

## Файловое хранилище (MinIO)

```bash
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=taskflow-files
MINIO_USE_SSL=false
```

## Email (Mailgun)

```bash
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@mg.taskflow.dev
SMTP_PASSWORD=your-mailgun-password
EMAIL_FROM=TaskFlow <noreply@taskflow.dev>
```

## Slack интеграция

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX
SLACK_CHANNEL=#taskflow-notifications
```

## Frontend

```bash
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8004
```

## Общие

```bash
# development / staging / production
ENVIRONMENT=development

# Уровень логирования: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO

# CORS (через запятую)
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

## Production-специфичные

В production переменные берутся из Azure Key Vault (не из .env файла):
- `db-password`
- `jwt-private-key`
- `rabbitmq-password`
- `minio-secret-key`
- `mailgun-api-key`
- `slack-webhook-url`

Подключение через Azure CSI Secret Store Driver. Конфигурация в `deploy/charts/*/templates/secret-provider.yaml`.
