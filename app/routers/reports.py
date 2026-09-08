from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.dependencies import (
    get_current_user_id,
    get_project_role,
    require_project_lead,
    require_project_member,
)
from app.exceptions import ForbiddenException, SprintNotFoundException
from app.repositories.reports import get_sprint
from app.schemas.reports import (
    ActivitySummary,
    BurndownReport,
    PaginatedActivity,
    VelocityReport,
)
from app.services.reports import (
    get_activity_feed,
    get_burndown,
    get_velocity,
    get_who_did_what,
)

router = APIRouter(prefix="/reports", tags=["reports"])

db = Annotated[AsyncIOMotorDatabase, Depends(get_database)]
CurrentUser = Annotated[UUID, Depends(get_current_user_id)]

@router.get("/projects/{project_id}/activity", response_model=PaginatedActivity)
async def activity(
    project_id: UUID, db: db, _member: Annotated[str, Depends(require_project_member)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    actor: UUID | None = None
) -> PaginatedActivity:
    return await get_activity_feed(project_id, limit, offset, db, actor)


@router.get("/projects/{project_id}/activity/summary", response_model=ActivitySummary)
async def who_did_what(project_id: UUID, db: db, user_id: CurrentUser, role: Annotated[str, Depends(require_project_member)]) -> ActivitySummary:
    # lead sees everyone, contributor sees only themselves.
    return await get_who_did_what(project_id, db, actor=None if role == "lead" else user_id)


@router.get("/projects/{project_id}/velocity", response_model=VelocityReport)
async def velocity(project_id: UUID, db: db, _lead: Annotated[str, Depends(require_project_lead)]) -> VelocityReport:
    return await get_velocity(project_id, db)


@router.get("/sprints/{sprint_id}/burndown", response_model=BurndownReport)
async def burndown(sprint_id: UUID, db: db, user_id: CurrentUser) -> BurndownReport:
    sprint = await get_sprint(sprint_id, db)
    if sprint is None:
        raise SprintNotFoundException

    if await get_project_role(user_id, sprint.project_id) != "lead":
        raise ForbiddenException

    return await get_burndown(sprint, db)