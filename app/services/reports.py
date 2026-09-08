from app.repositories.reports import (
    count_by_actor,
    get_activity_page,
    get_project_sprints,
    get_sprint,
    get_ticket_history,
)
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import date, datetime
from uuid import UUID
from app.schemas.reports import PaginatedActivity, ActivitySummary, ActorActivity, ActivityEvent, VelocityReport, SprintVelocity
from app.schemas.events import CreatedMetadata, UpdatedMetadata, SprintAssignmentMetadata, SprintMetadata


async def get_activity_feed(project_id: UUID, limit: int, offset: int, db: AsyncIOMotorDatabase, actor: UUID | None = None) -> PaginatedActivity:
    result, total = await get_activity_page(project_id, limit, offset, db, actor)
    return PaginatedActivity(count=total, limit=limit, offset=offset, result=result)

async def get_who_did_what(project_id: UUID, db: AsyncIOMotorDatabase, actor: UUID | None = None) -> ActivitySummary:
    rows = await count_by_actor(project_id, db, actor)

    buckets: dict[UUID, dict[str, int]] = {}
    for row in rows:
        key = row["_id"]
        buckets.setdefault(key["actor"], {})[key["action"]] = row["n"]

    actors = [
        ActorActivity(actor=actor_id, total=sum(actions.values()), by_action=actions) for actor_id, actions in buckets.items()
    ]
    actors.sort(key=lambda a: a.total, reverse=True)

    return ActivitySummary(project_id=project_id, total_events=sum(a.total for a in actors), actors=actors)

def build_ticket_states(events: list[ActivityEvent], until: datetime | None = None) -> dict[UUID, dict]:
    """Turn a list of changes into the current state of every ticket"""
    states: dict[UUID, dict] = {}

    for event in events:
        if until is not None and event.created_at > until:
            break
        ticket_id = event.entity_id
        md = event.metadata

        if event.action == "ticket.created" and isinstance(md, CreatedMetadata):
            states[ticket_id] = {"key": event.entity_key, "points": int(md.story_points) if md.story_points else None, "status": "todo", "sprint": None}

        elif event.action == "ticket.deleted":
            states.pop(ticket_id, None)

        elif ticket_id not in states:
            continue

        elif event.action == "ticket.updated" and isinstance(md, UpdatedMetadata):
            if md.field == "status":
                states[ticket_id]["status"] = md.to
            elif md.field == "story_points":
                states[ticket_id]["points"] = int(md.to) if md.to else None

        elif event.action == "ticket.sprint_added" and isinstance(md, SprintAssignmentMetadata):
            states[ticket_id]["sprint"] = md.sprint_id

        elif event.action == "ticket.sprint_removed":
            states[ticket_id]["sprint"] = None
    return states

async def get_velocity(project_id: UUID, db: AsyncIOMotorDatabase) -> VelocityReport:
    sprints = await get_project_sprints(project_id, db)
    events = await get_ticket_history(project_id, db)
    final = build_ticket_states(events)

    rows = []
    for sprint in sprints:
        md = sprint.metadata
        if not isinstance(md, SprintMetadata):
            continue
        sprint_id = sprint.entity_id
        at_start = build_ticket_states(events, until=sprint.created_at)

        committed = sum(t["points"] or 0 for t in at_start.values() if t["sprint"] == sprint_id)
        done = [t for t in final.values() if t["sprint"] == sprint_id and t["status"] == "done"]

        rows.append(SprintVelocity(
            sprint_id=sprint.entity_id,
            sprint_name=sprint.entity_key,
            start_date=date.fromisoformat(md.start_date) if md.start_date else None,
            end_date=date.fromisoformat(md.end_date) if md.end_date else None,
            committed_points=committed,
            completed_points=sum(t["points"] or 0 for t in done),
            completed_tickets=len(done),
        ))

    average = sum(r.completed_points for r in rows) / len(rows) if rows else 0.0
    return VelocityReport(project_id=project_id, sprints=rows, average_points=average)
