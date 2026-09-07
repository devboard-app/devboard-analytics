from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.events import ActivityEvent


async def get_activity_page(project_id: UUID, limit: int, offset: int, db: AsyncIOMotorDatabase, actor: UUID | None) -> tuple[list[ActivityEvent], int]:
    query = {"project_id": project_id}
    if actor is not None:
        query["actor"] = actor
    docs = await db.events.find(query).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    total = await db.events.count_documents({"project_id": project_id})
    return [ActivityEvent(**doc) for doc in docs], total

async def count_by_actor(project_id: UUID, db: AsyncIOMotorDatabase, actor: UUID | None = None) -> list[dict]:
    match = {"project_id": project_id}
    if actor is not None:
        match["actor"] = actor
    pipeline=[
        {"$match": match},
        {"$group": {"_id": {"actor": "$actor", "action": "$action"}, "n": {"$sum": 1}}}
    ]
    return await db.events.aggregate(pipeline).to_list(None)

