from redis import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine


def check_postgres() -> bool:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return result.scalar_one() == 1


def check_redis() -> bool:
    settings = get_settings()
    client = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=3,
        socket_timeout=3,
        decode_responses=True,
    )

    try:
        return bool(client.ping())
    finally:
        client.close()
