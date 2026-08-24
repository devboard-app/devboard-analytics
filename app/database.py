from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

client: AsyncIOMotorClient | None = None

async def connect_to_mongo() -> None:
    global client
    client = AsyncIOMotorClient(settings.MONGO_URI)
    await client.admin.command("ping")

async def close_mongo_connection() -> None:
    if client is not None:
        client.close()

def get_database() -> AsyncIOMotorDatabase:
    if client is None:
        raise RuntimeError("Mongo client is not initiated. Did the app startup run?")
    return client.get_default_database()