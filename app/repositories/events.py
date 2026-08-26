from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.schemas.events import ActivityEvent


async def insert_event(event: ActivityEvent, db: AsyncIOMotorDatabase) -> ActivityEvent:
    try:
        await db.events.insert_one(event.model_dump(by_alias=True))
    except DuplicateKeyError:
        pass
    return event

async def get_recent_events(db:AsyncIOMotorDatabase, limit: int = 10) -> list[ActivityEvent]:
    docs = await db.events.find().sort("created_at", -1).limit(limit).to_list(limit)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return [ActivityEvent(**doc) for doc in docs]
