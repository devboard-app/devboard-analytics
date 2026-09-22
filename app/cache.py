from typing import cast
from uuid import UUID

from redis.asyncio import Redis

from app.config import settings

REPORT_CACHE_TTL_SECONDS = 600  # backstop only -- normal invalidation is bump_report_version below

client: Redis | None = None


async def connect_to_redis() -> None:
    global client
    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis_connection() -> None:
    if client is not None:
        await client.aclose()


def get_redis() -> Redis:
    if client is None:
        raise RuntimeError("Redis client is not initiated. Did startup run?")
    return client


async def get_report_version(project_id: UUID) -> int:
    """Each project's version is bumped every time a new event is recorded
    for it. Report cache keys embed the version they were computed at, so a
    version bump makes every previously cached report for that project
    unreachable (orphaned, not deleted -- they just expire via TTL) without
    needing to know in advance which report keys exist for that project.
    """
    version = await get_redis().get(f"report_version:{project_id}")
    return int(version) if version else 0


async def bump_report_version(project_id: UUID) -> None:
    await get_redis().incr(f"report_version:{project_id}")


async def get_cached_report(cache_key: str) -> str | None:
    value = await get_redis().get(cache_key) or None
    return cast("str | None", value)


async def set_cached_report(cache_key: str, value: str) -> None:
    await get_redis().set(cache_key, value, ex=REPORT_CACHE_TTL_SECONDS)
