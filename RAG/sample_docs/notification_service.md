# Notification Service

## Обзор

Notification Service — микросервис на Node.js (Express), отвечающий за доставку уведомлений пользователям через email, WebSocket и Slack webhook.

## Как работает

1. Task Service или Auth Service публикуют событие в RabbitMQ exchange
2. Notification Service потребляет сообщения из привязанных очередей
3. На основе типа события выбирается шаблон уведомления
4. Уведомление отправляется через нужные каналы

## Типы событий

| Exchange | Routing Key | Описание | Каналы |
|----------|-------------|----------|--------|
| task.events | task.created | Новая задача | WebSocket |
| task.events | task.assigned | Задача назначена | Email, WebSocket |
| task.events | task.status_changed | Смена статуса | WebSocket |
| task.events | task.commented | Новый комментарий | Email, WebSocket |
| task.events | task.due_soon | Дедлайн через 24ч | Email, Slack |
| user.events | user.registered | Новый пользователь | Email (welcome) |

## Шаблоны email

Шаблоны хранятся в MongoDB, коллекция `templates`. Формат — Handlebars.

Пример шаблона для `task.assigned`:
```handlebars
<h2>Вам назначена задача</h2>
<p>{{assignerName}} назначил вам задачу 
   <a href="{{taskUrl}}">{{taskTitle}}</a> 
   в проекте {{projectName}}.</p>
<p>Приоритет: <strong>{{priority}}</strong></p>
{{#if dueDate}}
<p>Дедлайн: {{formatDate dueDate}}</p>
{{/if}}
```

## WebSocket

Клиент подключается через `ws://localhost:8004/ws?token=<access_token>`.

Формат сообщений:
```json
{
  "type": "task.status_changed",
  "payload": {
    "task_id": "...",
    "old_status": "in_progress",
    "new_status": "review",
    "changed_by": "Иван Петров"
  },
  "timestamp": "2024-02-01T10:30:00Z"
}
```

Сервис хранит Map `userId → Set<WebSocket>` для маршрутизации сообщений нужному пользователю.

## Конфигурация

Переменные окружения:
| Переменная | Описание | Default |
|------------|----------|---------|
| RABBITMQ_URL | URL подключения к RabbitMQ | amqp://guest:guest@rabbitmq:5672 |
| MONGODB_URL | URL подключения к MongoDB | mongodb://mongodb:27017/notifications |
| SMTP_HOST | SMTP сервер | smtp.mailgun.org |
| SMTP_PORT | SMTP порт | 587 |
| SMTP_USER | SMTP пользователь | — |
| SMTP_PASS | SMTP пароль | — |
| SLACK_WEBHOOK_URL | Slack webhook | — |
| WS_PORT | Порт WebSocket сервера | 8004 |
| JWT_PUBLIC_KEY | Публичный ключ для проверки JWT | — |

## Retry-логика

При ошибке отправки email:
- 3 попытки с экспоненциальным backoff (1с, 5с, 25с)
- После 3 неудач — сообщение перемещается в Dead Letter Queue
- DLQ обрабатывается вручную через скрипт `scripts/retry_dlq.js`

## Мониторинг

Метрики (Prometheus):
- `notifications_sent_total{channel, event_type}` — счётчик отправленных уведомлений
- `notifications_failed_total{channel, event_type}` — счётчик ошибок
- `ws_connections_active` — текущее количество WebSocket соединений
- `rabbitmq_messages_consumed_total` — количество обработанных сообщений
