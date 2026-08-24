from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.events import insert_event
from app.schemas.events import ActivityEvent


async def record_event(event: ActivityEvent, db: AsyncIOMotorDatabase) -> ActivityEvent:
    return await insert_event(event, db)
