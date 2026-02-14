# Безопасность TaskFlow

## Принципы

- Принцип наименьших привилегий: каждый сервис имеет доступ только к своей БД
- Defense in depth: валидация на клиенте, API Gateway и в сервисе
- Secrets никогда не хранятся в коде или Git

## Аутентификация

Подробности — в документе auth_flow.md. Ключевые моменты:
- JWT с RS256 (асимметричная подпись)
- Access token: 30 мин, refresh token: 7 дней
- Refresh token rotation с детекцией кражи
- Пароли: bcrypt с cost factor 12

## Защита API

### Rate Limiting
Настроен на Kong API Gateway:
- Аутентифицированные пользователи: 100 req/min
- Эндпоинт /login: 5 req/min (защита от brute force)
- Эндпоинт /register: 3 req/min

### Input Validation
Все входные данные проходят валидацию через Pydantic:
- Строковые поля: ограничение длины, regex при необходимости
- UUID: проверка формата
- Enum-поля: допустимые значения
- SQL injection: параметризованные запросы через SQLAlchemy
- XSS: экранирование при рендеринге Markdown (sanitize-html на фронте)

### CORS
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Только конкретные origins
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=True,
)
```

## Хранение секретов

### Локальная разработка
- `.env` файл (в .gitignore)
- JWT ключи в `keys/` (в .gitignore)
- Шаблон: `.env.example` с placeholder-значениями

### Production
- Azure Key Vault
- Секреты монтируются в поды через CSI Secret Store Driver
- Ротация секретов: Key Vault автоматически обновляет, поды подхватывают через 2 минуты

## Зависимости

- `pip-audit` и `npm audit` запускаются в CI pipeline
- Dependabot включён на GitHub (еженедельная проверка)
- Критические CVE: обновление в течение 24 часов
- Docker-образы: используем alpine-варианты для минимизации attack surface

## Логирование безопасности

События, которые логируются с уровнем WARNING или выше:
- Неудачные попытки входа
- Использование отозванного refresh token (потенциальная кража)
- Попытки доступа к чужим ресурсам (403)
- Rate limit exceeded (429)
- Невалидные JWT-токены

Эти события мониторятся через Kibana dashboard "Security Events".
