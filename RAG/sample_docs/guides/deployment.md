# Процесс деплоя TaskFlow

## Окружения

| Окружение | URL | Кластер | Деплой |
|-----------|-----|---------|--------|
| Development | http://localhost:3000 | Docker Compose | Ручной |
| Staging | https://staging.taskflow.internal | AKS staging | Автоматический из develop |
| Production | https://taskflow.internal | AKS production | Ручной approve после staging |

## CI/CD Pipeline (Azure DevOps)

Pipeline описан в файле `azure-pipelines.yml` в корне монорепо.

### Этапы pipeline

**1. Lint & Check (при каждом коммите)**
- Python: ruff check + black --check + mypy
- TypeScript: eslint + tsc --noEmit
- Dockerfile: hadolint

**2. Test (при каждом коммите)**
- Python: pytest с покрытием (минимум 80%)
- TypeScript: vitest
- Отчёт о покрытии публикуется как артефакт

**3. Build (при merge в develop или main)**
- Docker build для каждого сервиса
- Образы тегируются: `{service}:{branch}-{commit_sha}`
- Push в Azure Container Registry (taskflow.azurecr.io)

**4. Deploy Staging (автоматически при merge в develop)**
- Helm upgrade в staging namespace
- Ожидание readiness probes (timeout 5 минут)
- Запуск smoke tests
- При провале — автоматический rollback

**5. Deploy Production (ручной approve)**
- После успешного staging deploy создаётся Release
- Требуется approve от tech lead или team lead
- Blue-green deployment: новые поды поднимаются параллельно
- После проверки health checks — переключение трафика
- Старые поды живут 10 минут (быстрый rollback при проблемах)

## Kubernetes

### Helm Chart
Каждый сервис имеет свой Helm chart в `deploy/charts/{service-name}/`.

Общие значения вынесены в `deploy/charts/values-staging.yaml` и `deploy/charts/values-production.yaml`.

### Ресурсы (production)

| Сервис | Replicas | CPU | Memory |
|--------|----------|-----|--------|
| Auth Service | 2 | 250m | 256Mi |
| Task Service | 3 | 500m | 512Mi |
| Notification Service | 2 | 250m | 256Mi |
| File Service | 2 | 250m | 512Mi |
| Frontend (nginx) | 2 | 100m | 128Mi |

### Health Checks
Все сервисы реализуют два эндпоинта:
- `GET /health/live` — liveness probe (процесс работает)
- `GET /health/ready` — readiness probe (подключение к БД, RabbitMQ в порядке)

## Секреты

Секреты хранятся в Azure Key Vault и подключаются через CSI driver:
- `db-password` — пароли к PostgreSQL
- `jwt-private-key` — приватный ключ для подписи JWT
- `rabbitmq-password` — пароль RabbitMQ
- `minio-secret-key` — ключ MinIO
- `mailgun-api-key` — ключ Mailgun для email

Локально секреты берутся из `.env` файла (не коммитится, шаблон в `.env.example`).

## Rollback

### Автоматический
- Если readiness probe не проходит 3 раза подряд — Kubernetes откатывает deployment
- Если smoke tests на staging падают — Helm rollback

### Ручной
```bash
# Посмотреть историю релизов
helm history task-service -n production

# Откатить на предыдущую версию
helm rollback task-service 1 -n production

# Откатить конкретный сервис через pipeline
# В Azure DevOps: Releases → выбрать релиз → Rollback
```

## Мониторинг после деплоя

После каждого production deploy команда обязана 15 минут следить за:
- Grafana дашборд "Post-Deploy" (error rate, latency p99, CPU/memory)
- Kibana: фильтр по `deployment_id` последнего деплоя
- RabbitMQ: нет ли роста unacked messages
