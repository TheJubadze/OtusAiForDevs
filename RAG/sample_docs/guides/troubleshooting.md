# Troubleshooting — Частые проблемы и решения

## Локальная разработка

### Docker Compose не стартует, порт занят
**Симптом:** `Bind for 0.0.0.0:5432 failed: port is already allocated`

**Решение:** Найдите и остановите процесс, занимающий порт:
```bash
# Linux/Mac
lsof -i :5432
kill <PID>

# Или остановите локальный PostgreSQL
sudo systemctl stop postgresql
```

### Миграции падают при первом запуске
**Симптом:** `relation "users" does not exist`

**Причина:** Task Service стартует раньше, чем PostgreSQL полностью инициализируется.

**Решение:** Перезапустите сервис:
```bash
docker compose restart task-service
# или дождитесь healthcheck и запустите вручную
docker compose exec task-service alembic upgrade head
```

### Фронтенд показывает "Network Error"
**Симптом:** Все API-запросы возвращают ошибку.

**Проверьте:**
1. Kong запущен: `curl http://localhost:8000/api/health`
2. CORS настроен: в `.env` переменная `CORS_ORIGINS=http://localhost:3000`
3. Токен не протух: в DevTools → Application → Cookies → проверьте refresh_token

### RabbitMQ не принимает сообщения
**Симптом:** Задачи создаются, но уведомления не приходят.

**Проверьте:**
1. RabbitMQ UI: http://localhost:15672 (guest/guest)
2. Exchanges: должны существовать `task.events` и `user.events`
3. Queues: `notification.task_events` должна быть привязана к exchange
4. Если очередей нет — перезапустите Notification Service:
   ```bash
   docker compose restart notification-service
   ```

## Staging / Production

### 502 Bad Gateway после деплоя
**Причина:** Новые поды ещё не прошли readiness check.

**Действия:**
1. Подождите 2–3 минуты
2. Проверьте поды: `kubectl get pods -n staging -l app=task-service`
3. Если поды в CrashLoopBackOff — посмотрите логи:
   ```bash
   kubectl logs -n staging -l app=task-service --tail=100
   ```
4. Частая причина: не хватает переменных окружения или секретов. Проверьте:
   ```bash
   kubectl describe pod <pod-name> -n staging
   ```

### Высокий latency на Task Service
**Симптом:** API отвечает дольше 2 секунд.

**Диагностика:**
1. Grafana → дашборд "Task Service" → найдите медленные эндпоинты
2. Часто причина — N+1 запросы при загрузке задач с labels и assignees
3. Проверьте slow queries в PostgreSQL:
   ```sql
   SELECT query, mean_exec_time, calls
   FROM pg_stat_statements
   ORDER BY mean_exec_time DESC
   LIMIT 10;
   ```
4. Убедитесь, что индексы на месте (см. database_schema.md)

### Out of Memory на Notification Service
**Симптом:** Pod перезапускается с OOMKilled.

**Причина:** Утечка памяти при накоплении WebSocket-соединений.

**Решение:**
1. Временно: увеличьте memory limit до 512Mi
2. Долгосрочно: проверьте, что отключённые клиенты корректно удаляются из Map
3. Мониторинг: настройте alert на memory > 80% от limit

### Потеря сообщений в RabbitMQ
**Симптом:** Часть уведомлений не доставлена.

**Проверьте:**
1. Dead letter queue: `dlq.notification.task_events` — там скапливаются необработанные сообщения
2. Причина обычно — ошибка десериализации (сервисы используют разные версии схемы)
3. Решение: обновите оба сервиса до одной версии schema

## Типичные ошибки в коде

### "Task not found" при обновлении задачи
**Причина:** Frontend отправляет task_id из кеша, который уже удалён.

**Решение:** Обрабатывайте 404 на фронте, инвалидируйте кеш:
```typescript
// В useUpdateTask hook
onError: (error) => {
  if (error.status === 404) {
    queryClient.invalidateQueries(['tasks']);
    toast.error('Задача была удалена другим пользователем');
  }
}
```

### Дублирование уведомлений
**Причина:** Notification Service получает сообщение, обрабатывает, но не успевает отправить ACK — RabbitMQ повторно доставляет.

**Решение:** Реализована идемпотентность через таблицу `delivery_log` с уникальным constraint на `(event_id, channel)`. Если дубль — INSERT игнорируется через `ON CONFLICT DO NOTHING`.
