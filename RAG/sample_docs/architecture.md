# Архитектура проекта TaskFlow

## Обзор

TaskFlow — внутренняя система управления задачами и проектами, разработанная для команд от 5 до 50 человек. Система построена по микросервисной архитектуре с API Gateway в качестве единой точки входа.

## Основные компоненты

### API Gateway (Kong)
Все входящие HTTP-запросы проходят через Kong API Gateway, который выполняет:
- Маршрутизацию запросов к нужному микросервису
- Rate limiting (100 запросов в минуту на пользователя)
- JWT-валидацию токенов
- Логирование запросов в формате JSON

### Auth Service (Python, FastAPI)
Сервис аутентификации и авторизации. Использует JWT-токены с временем жизни 30 минут для access token и 7 дней для refresh token. Хранит пользователей в PostgreSQL. Поддерживает RBAC с тремя ролями: admin, manager, member.

### Task Service (Python, FastAPI)
Основной сервис для работы с задачами. Отвечает за CRUD задач, проектов и спринтов. Использует собственную базу PostgreSQL. Взаимодействует с Notification Service через RabbitMQ при изменении статуса задачи.

### Notification Service (Node.js, Express)
Обрабатывает очередь событий из RabbitMQ и отправляет уведомления:
- Email через SMTP (Mailgun)
- WebSocket для real-time обновлений в браузере
- Webhook для интеграции со Slack

### File Service (Python, FastAPI)
Хранение и обработка файлов-вложений к задачам. Файлы хранятся в MinIO (S3-совместимое хранилище). Максимальный размер файла — 50 MB. Поддерживаемые форматы: изображения, PDF, документы Office.

## Базы данных

Каждый сервис имеет собственную базу данных (Database per Service pattern):
- **auth_db** — PostgreSQL 15, таблицы: users, roles, permissions, refresh_tokens
- **task_db** — PostgreSQL 15, таблицы: projects, sprints, tasks, comments, labels, task_labels
- **notification_db** — MongoDB, коллекции: notifications, templates, delivery_log

## Межсервисное взаимодействие

- Синхронное: REST API через Kong (сервис → Kong → сервис)
- Асинхронное: RabbitMQ (exchanges: task.events, user.events)

## Инфраструктура

- Docker Compose для локальной разработки
- Kubernetes (Azure AKS) для production
- CI/CD: Azure DevOps Pipelines
- Мониторинг: Prometheus + Grafana
- Логирование: ELK Stack (Elasticsearch, Logstash, Kibana)

## Схема взаимодействия

```
Client (React SPA)
      │
      ▼
  Kong API Gateway (:8000)
      │
      ├── /api/auth/*    → Auth Service (:8001)
      ├── /api/tasks/*   → Task Service (:8002)
      ├── /api/files/*   → File Service (:8003)
      └── /ws/*          → Notification Service (:8004)
      
RabbitMQ (:5672) ← Task Service → Notification Service
```
