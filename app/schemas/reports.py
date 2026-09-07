from datetime import date
from uuid import UUID

from pydantic import BaseModel

from app.schemas.events import ActivityEvent


class PaginatedActivity(BaseModel):
    count: int
    limit: int
    offset: int
    result: list[ActivityEvent]

class ActorActivity(BaseModel):
    actor: UUID
    total: int
    by_action: dict[str, int]

class SprintVelocity(BaseModel):
    sprint_id: UUID
    sprint_name: str
    start_date: date | None
    end_date: date | None
    committed_points: int
    completed_points: int
    completed_tickets: int

class VelocityReport(BaseModel):
    project_id: UUID
    sprints: list[SprintVelocity]
    average_points: float

class BurndownDay(BaseModel):
    day: date
    remaining_points: int
    remaining_tickets: int
    ideal_points: float

class BurndownReport(BaseModel):
    sprint_id: UUID
    sprint_name: str
    start_date: date
    end_date: date
    committed_points: int
    unpointed_tickets: int
    days: list[BurndownDay]