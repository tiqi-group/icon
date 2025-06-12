import redis

from icon.config.config import get_config


def valkey_url() -> str:
    cfg = get_config().databases.valkey
    return f"redis://{cfg.host}:{cfg.port}/0"


def is_valkey_available() -> bool:
    try:
        redis.Redis.from_url(valkey_url()).ping()
        return True
    except redis.RedisError:
        return False
