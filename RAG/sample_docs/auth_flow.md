# Авторизация и аутентификация в TaskFlow

## Общая схема

TaskFlow использует JWT (JSON Web Tokens) для аутентификации. Реализована схема с двумя токенами: access token (короткоживущий) и refresh token (долгоживущий).

## Процесс входа (Login Flow)

1. Пользователь отправляет `POST /api/auth/login` с email и паролем
2. Auth Service проверяет пароль через bcrypt.checkpw()
3. Если пароль верный, генерируются два токена:
   - **Access Token** (JWT, срок жизни 30 минут) — содержит user_id, role, permissions
   - **Refresh Token** (opaque string, срок жизни 7 дней) — сохраняется в таблицу refresh_tokens
4. Оба токена возвращаются клиенту
5. Клиент сохраняет access token в памяти (не в localStorage!), refresh token — в httpOnly cookie

## Структура Access Token (JWT payload)

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "email": "ivan@taskflow.dev",
  "role": "manager",
  "permissions": ["task:create", "task:edit", "task:delete", "project:view", "sprint:manage"],
  "iat": 1700000000,
  "exp": 1700001800
}
```

## Обновление токена (Refresh Flow)

1. Клиент получает 401 Unauthorized от любого сервиса
2. Клиент отправляет `POST /api/auth/refresh` с refresh token из cookie
3. Auth Service проверяет: токен существует, не отозван, не истёк
4. Генерирует новую пару access + refresh token
5. Старый refresh token помечается как отозванный (rotation)

## Роли и разрешения (RBAC)

### Admin
- Полный доступ ко всем ресурсам
- Управление пользователями (создание, блокировка)
- Управление ролями и разрешениями
- Удаление проектов

### Manager
- Создание и управление проектами
- Управление спринтами
- Назначение задач на участников
- Просмотр отчётов по всем проектам

### Member
- Создание и редактирование своих задач
- Просмотр задач в назначенных проектах
- Комментирование задач
- Обновление статуса назначенных задач

## Валидация JWT в API Gateway

Kong проверяет JWT при каждом запросе к защищённым эндпоинтам:
1. Извлекает токен из заголовка `Authorization: Bearer <token>`
2. Проверяет подпись (алгоритм RS256, публичный ключ из Auth Service)
3. Проверяет срок действия (exp claim)
4. Добавляет заголовки `X-User-ID` и `X-User-Role` в проксированный запрос

Незащищённые эндпоинты (не требуют JWT):
- `POST /api/auth/login`
- `POST /api/auth/register`
- `POST /api/auth/refresh`
- `GET /api/health`

## Безопасность

- Пароли хешируются через bcrypt с cost factor 12
- Refresh token rotation: каждый использованный refresh token отзывается
- При обнаружении использования отозванного refresh token — все токены пользователя отзываются (potential theft detection)
- Rate limiting на login: 5 попыток в минуту
- CORS: разрешён только origin фронтенда (http://localhost:3000 для dev)
