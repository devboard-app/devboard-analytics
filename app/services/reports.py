from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.exceptions import SprintWindowMissingException
from app.repositories.reports import (
    count_by_actor,
    get_activity_page,
    get_project_sprints,
    get_ticket_history,
)
from app.schemas.events import (
    CreatedMetadata,
    SprintAssignmentMetadata,
    SprintMetadata,
    UpdatedMetadata,
)
from app.schemas.reports import (
    ActivityEvent,
    ActivitySummary,
    ActorActivity,
    BurndownDay,
    BurndownReport,
    PaginatedActivity,
    SprintVelocity,
    VelocityReport,
)


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
    """How many points each sprint took on, and how many it delivered.
    Example:
        {
          "project_id": "5a69519f-bcb0-5329-b152-3f767ee3c484",
          "average_points": 20.0,
          "sprints": [
            {
              "sprint_id": "bd590c73-bdb4-528c-9cbc-d0995b0137c1",
              "sprint_name": "Sprint 1",
              "start_date": "2026-08-13",
              "end_date": "2026-08-27",
              "committed_points": 40,
              "completed_points": 27,
              "completed_tickets": 7
            },
            {
              "sprint_id": "4260b207-f709-56f4-9db3-3769960bbdc8",
              "sprint_name": "Sprint 2",
              "start_date": "2026-09-02",
              "end_date": "2026-09-12",
              "committed_points": 20,
              "completed_points": 13,
              "completed_tickets": 4
            }
          ]
        }
    """
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

async def get_burndown(sprint: ActivityEvent, db: AsyncIOMotorDatabase) -> BurndownReport:
    """Remaining work per day of a sprint, nex to the ideal line
        remaining_points(real line) + ideal_points (guideline) vs time"""
    md = sprint.metadata
    if not isinstance(md, SprintMetadata) or not md.start_date or not md.end_date:
        raise SprintWindowMissingException

    start = date.fromisoformat(md.start_date)
    end = date.fromisoformat(md.end_date)

    events = await get_ticket_history(sprint.project_id, db)

    at_start = build_ticket_states(events, until=sprint.created_at)
    committed = sum(t["points"] or 0 for t in at_start.values() if t["sprint"] == sprint.entity_id)

    all_days: list[date] =[]
    day = start
    while day <= end:
        all_days.append(day)
        day += timedelta(days=1)

    work_days = [d for d in all_days if d.weekday() < 5]
    steps = max(len(work_days) - 1, 1)

    def ideal_for(current: date) -> float:
        elapsed = max(sum(1 for w in work_days if w <= current) - 1, 0)
        return round(committed * (1 - elapsed / steps), 2)

    today = datetime.now(timezone.utc).date()
    days: list[BurndownDay] = []
    unpointed = 0

    for current in all_days:
        if current > today:
            break

        cutoff = datetime.combine(current, time.max) # today 23:59:59.999
        states = build_ticket_states(events, until=cutoff)

        in_sprint = [t for t in states.values() if t["sprint"] == sprint.entity_id]
        open_tickets = [t for t in in_sprint if t["status"] != "done"]

        days.append(BurndownDay(
            day=current,
            remaining_points=sum(t["points"] or 0 for t in open_tickets),
            remaining_tickets=len(open_tickets),
            ideal_points=ideal_for(current),
        ))
        unpointed = sum(1 for t in in_sprint if t["points"] is None)

    return BurndownReport(
        sprint_id=sprint.entity_id,
        sprint_name=sprint.entity_key,
        start_date=start,
        end_date=end,
        committed_points=committed,
        unpointed_tickets=unpointed,
        days=days
    )