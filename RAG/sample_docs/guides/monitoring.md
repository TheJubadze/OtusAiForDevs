# Мониторинг и алертинг

## Стек мониторинга

- **Prometheus** — сбор метрик с сервисов (pull model, scrape interval 15s)
- **Grafana** — визуализация метрик, дашборды
- **ELK Stack** — логирование (Elasticsearch + Logstash + Kibana)
- **AlertManager** — маршрутизация алертов в Slack и PagerDuty

## Дашборды Grafana

### Overview Dashboard
Общая картина здоровья системы:
- Request rate (req/sec) по сервисам
- Error rate (% запросов с 5xx)
- Latency P50, P95, P99 по сервисам
- CPU и Memory по подам

### Task Service Dashboard
- Количество созданных/завершённых задач за день
- Распределение запросов по эндпоинтам
- Slow queries (>500ms)
- Размер connection pool PostgreSQL

### Post-Deploy Dashboard
Используется 15 минут после каждого деплоя:
- Error rate до и после деплоя (сравнение)
- Latency P99 до и после
- Новые типы ошибок в логах
- Memory/CPU тренд

## Метрики приложений

Все Python-сервисы экспортируют метрики через `prometheus-fastapi-instrumentator`:

```python
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

Кастомные метрики:
```python
from prometheus_client import Counter, Histogram

tasks_created_total = Counter(
    "tasks_created_total",
    "Total number of tasks created",
    ["project_id", "priority"],
)

task_creation_duration = Histogram(
    "task_creation_duration_seconds",
    "Time to create a task",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)
```

## Алерты

### Critical (PagerDuty — немедленная реакция)
| Алерт | Условие | Описание |
|-------|---------|----------|
| HighErrorRate | error_rate > 5% за 5 мин | Массовые ошибки |
| ServiceDown | up == 0 за 2 мин | Сервис не отвечает |
| DatabaseDown | pg_up == 0 за 1 мин | PostgreSQL недоступен |

### Warning (Slack — реакция в рабочие часы)
| Алерт | Условие | Описание |
|-------|---------|----------|
| HighLatency | p99 > 2s за 10 мин | Высокий latency |
| HighMemory | memory > 80% limit | Высокое потребление памяти |
| RabbitMQBacklog | unacked > 1000 | Очередь растёт |
| DiskSpace | disk_usage > 85% | Место на диске заканчивается |

## Логирование

Формат логов — structured JSON:
```json
{
  "timestamp": "2024-02-01T10:30:00.123Z",
  "level": "ERROR",
  "service": "task-service",
  "trace_id": "abc123",
  "message": "Failed to create task",
  "error": "IntegrityError: duplicate key",
  "user_id": "550e8400-...",
  "endpoint": "POST /api/tasks/tasks",
  "duration_ms": 45
}
```

Все логи отправляются в stdout, Logstash собирает их из Docker/Kubernetes и отправляет в Elasticsearch.

### Полезные запросы в Kibana

Ошибки за последний час:
```
level: "ERROR" AND service: "task-service" AND @timestamp > now-1h
```

Медленные запросы:
```
duration_ms > 1000 AND service: "task-service"
```

Запросы конкретного пользователя:
```
user_id: "550e8400-..." AND @timestamp > now-24h
```
