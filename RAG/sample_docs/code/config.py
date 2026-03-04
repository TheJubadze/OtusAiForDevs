"""
Конфигурация Task Service.
Все настройки загружаются из переменных окружения через Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Настройки Task Service.
    
    Все параметры могут быть переопределены через переменные окружения.
    Например, DATABASE_URL можно задать через переменную TASK_SERVICE_DATABASE_URL.
    """

    # База данных
    database_url: str = Field(
        default="postgresql+asyncpg://taskflow:taskflow@localhost:5432/task_db",
        description="URL подключения к PostgreSQL",
    )
    db_pool_size: int = Field(default=10, description="Размер пула соединений")
    db_max_overflow: int = Field(default=20, description="Максимум дополнительных соединений")

    # RabbitMQ
    rabbitmq_url: str = Field(
        default="amqp://guest:guest@localhost:5672/",
        description="URL подключения к RabbitMQ",
    )

    # Сервис авторизации (для валидации user_id)
    auth_service_url: str = Field(
        default="http://auth-service:8001",
        description="URL Auth Service для внутренних запросов",
    )

    # JWT (только публичный ключ для проверки токенов)
    jwt_public_key_path: str = Field(
        default="/app/keys/jwt_public.pem",
        description="Путь к публичному ключу JWT",
    )

    # Общие настройки
    debug: bool = Field(default=False, description="Режим отладки")
    log_level: str = Field(default="INFO", description="Уровень логирования")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Разрешённые CORS origins",
    )

    # Пагинация
    default_page_size: int = Field(default=20, description="Размер страницы по умолчанию")
    max_page_size: int = Field(default=100, description="Максимальный размер страницы")

    model_config = {
        "env_prefix": "TASK_SERVICE_",
        "env_file": ".env",
    }


settings = Settings()
