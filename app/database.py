from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from redis.asyncio import Redis
from pymongo import ASCENDING, DESCENDING

from app.config import settings

client: AsyncIOMotorClient | None = None
redis_client: Redis | None = None

async def connect_to_mongo() -> None:
    global client
    client = AsyncIOMotorClient(settings.MONGO_URI, uuidRepresentation="standard")
    await client.admin.command("ping")

async def connect_to_redis() -> None:
    global redis_client
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis_client.ping()

async def close_mongo_connection() -> None:
    if client is not None:
        client.close()
async def close_redis_connection() -> None:
    if redis_client is not None:
        await redis_client.close()
        
def get_database() -> AsyncIOMotorDatabase:
    if client is None:
        raise RuntimeError("Mongo client is not initiated. Did the app startup run?")
    return client.get_default_database()

async def ensure_indexes() -> None:
    db = get_database()
    await db.events.create_index([("created_at", DESCENDING)])
    await db.events.create_index([("project_id", ASCENDING), ("created_at", DESCENDING)])
    await db.events.create_index([("entity_type", ASCENDING), ("entity_id", ASCENDING)])
    await db.events.create_index([("actor", ASCENDING), ("created_at", DESCENDING)])


