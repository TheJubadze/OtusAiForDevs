"""
Модуль публикации событий в RabbitMQ.

Используется Task Service для отправки событий о создании, обновлении
и удалении задач. Notification Service потребляет эти события и
отправляет уведомления пользователям.
"""

import json
import logging
from typing import Any

import aio_pika
from aio_pika import ExchangeType

from app.config import settings

logger = logging.getLogger(__name__)

_connection: aio_pika.RobustConnection | None = None
_channel: aio_pika.Channel | None = None


async def get_connection() -> aio_pika.RobustConnection:
    """Получение или создание подключения к RabbitMQ.
    
    Использует Robust Connection, который автоматически переподключается
    при потере связи.

    Returns:
        Активное подключение к RabbitMQ.
    """
    global _connection
    if _connection is None or _connection.is_closed:
        _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        logger.info("Connected to RabbitMQ at %s", settings.rabbitmq_url)
    return _connection


async def get_channel() -> aio_pika.Channel:
    """Получение или создание канала RabbitMQ.
    
    Returns:
        Активный канал.
    """
    global _channel
    if _channel is None or _channel.is_closed:
        connection = await get_connection()
        _channel = await connection.channel()
    return _channel


async def publish_event(
    exchange: str,
    routing_key: str,
    body: dict[str, Any],
) -> None:
    """Публикация события в RabbitMQ exchange.

    Сообщение сериализуется в JSON и отправляется с persistent delivery mode,
    чтобы не потерять сообщения при перезапуске RabbitMQ.

    Args:
        exchange: Имя exchange (например, 'task.events').
        routing_key: Routing key (например, 'task.created').
        body: Тело сообщения (будет сериализовано в JSON).

    Raises:
        aio_pika.exceptions.AMQPError: При ошибке подключения после retry.

    Example:
        >>> await publish_event(
        ...     exchange="task.events",
        ...     routing_key="task.created",
        ...     body={"task_id": "123", "title": "New task"},
        ... )
    """
    try:
        channel = await get_channel()

        # Объявляем exchange (idempotent)
        ex = await channel.declare_exchange(
            exchange,
            ExchangeType.TOPIC,
            durable=True,
        )

        message = aio_pika.Message(
            body=json.dumps(body).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await ex.publish(message, routing_key=routing_key)
        logger.debug(
            "Published event: exchange=%s, key=%s, body=%s",
            exchange,
            routing_key,
            body,
        )

    except Exception:
        logger.exception(
            "Failed to publish event: exchange=%s, key=%s",
            exchange,
            routing_key,
        )
        # Сбрасываем канал, чтобы при следующей попытке создался новый
        global _channel
        _channel = None
        raise


async def close_connection() -> None:
    """Закрытие подключения к RabbitMQ.
    
    Вызывается при shutdown приложения.
    """
    global _connection, _channel
    if _channel and not _channel.is_closed:
        await _channel.close()
    if _connection and not _connection.is_closed:
        await _connection.close()
    _connection = None
    _channel = None
    logger.info("RabbitMQ connection closed")
```
