from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.events import ActivityEvent

STATE_ACTIONS = [
    "ticket.created",
    "ticket.updated",
    "ticket.sprint_added",
    "ticket.sprint_removed",
    "ticket.deleted"
]

def _to_events(docs: list[dict]) -> list[ActivityEvent]:
    """Mongo returns raw dicts. ActivityEvent wants _id as a string not UUID(...)"""
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return [ActivityEvent(**doc) for doc in docs]

async def get_activity_page(project_id: UUID, limit: int, offset: int, db: AsyncIOMotorDatabase, actor: UUID | None) -> tuple[list[ActivityEvent], int]:
    """One page of the project feed, newest first. Total counts every matching row, not the page"""
    query = {"project_id": project_id}
    if actor is not None:
        query["actor"] = actor
    docs = await db.events.find(query).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    total = await db.events.count_documents(query)
    return _to_events(docs), total

async def count_by_actor(project_id: UUID, db: AsyncIOMotorDatabase, actor: UUID | None = None) -> list[dict]:
    """Counts per (actor, action) pair."""
    match = {"project_id": project_id}
    if actor is not None:
        match["actor"] = actor
    pipeline=[
        {"$match": match},
        {"$group": {"_id": {"actor": "$actor", "action": "$action"}, "n": {"$sum": 1}}}
    ]
    return await db.events.aggregate(pipeline).to_list(None)

async def get_ticket_history(project_id: UUID, db: AsyncIOMotorDatabase) -> list[ActivityEvent]:
    """State-changing ticket events, OLDEST first"""
    query = {"project_id": project_id, "action": {"$in": STATE_ACTIONS}}
    docs = await db.events.find(query).sort("created_at", 1).to_list(None)
    return _to_events(docs)

async def get_project_sprints(project_id: UUID, db: AsyncIOMotorDatabase) -> list[ActivityEvent]:
    """Every sprint in a project. sprint.started is the only event carrying the data"""
    query = {"project_id": project_id, "action": "sprint.started"}
    docs = await db.events.find(query).sort("created_at", 1).to_list(None)
    return _to_events(docs)

async def get_sprint(sprint_id: UUID, db: AsyncIOMotorDatabase) -> ActivityEvent | None:
    """Returns one sprint for chart data window"""
    doc = await db.events.find_one({"action": "sprint.started", "entity_type": "sprint", "entity_id": sprint_id})
    if doc is None:
        return None
    return _to_events([doc])[0]