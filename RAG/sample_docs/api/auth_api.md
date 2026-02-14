# API Reference — Auth Service

Base URL: `http://localhost:8000/api/auth`

## Аутентификация

### POST /login
Вход в систему.

**Body:**
```json
{
  "email": "ivan@taskflow.dev",
  "password": "string"
}
```

**Ответ (200):**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```
Refresh token устанавливается в httpOnly cookie `refresh_token`.

**Ошибки:**
- 401: Неверный email или пароль
- 429: Превышен лимит попыток (5/мин)

### POST /register
Регистрация нового пользователя. По умолчанию присваивается роль `member`.

**Body:**
```json
{
  "email": "string (valid email)",
  "password": "string (мин. 8 символов, буквы + цифры)",
  "full_name": "string (2-100 символов)"
}
```

**Валидация пароля:**
- Минимум 8 символов
- Хотя бы одна заглавная буква
- Хотя бы одна цифра
- Не совпадает с email

**Ответ (201):** Аналогично /login (автоматический вход после регистрации).

### POST /refresh
Обновление access token.

Refresh token берётся из httpOnly cookie. Новый refresh token возвращается в cookie (token rotation).

**Ответ (200):** Аналогично /login.

### POST /logout
Отзыв refresh token.

**Ответ (204):** Cookie удаляется, refresh token помечается как отозванный.

## Пользователи

### GET /users/me
Профиль текущего пользователя.

**Ответ (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "ivan@taskflow.dev",
  "full_name": "Иван Петров",
  "role": "manager",
  "permissions": ["task:create", "task:edit", "project:view"],
  "created_at": "2024-01-01T00:00:00Z",
  "last_login": "2024-02-01T09:15:00Z"
}
```

### PATCH /users/me
Обновление профиля. Можно менять full_name и password.

### GET /users
Список пользователей (для назначения задач). Требует роль admin или manager.

**Query параметры:** search (поиск по имени/email), role, is_active, page, per_page.
