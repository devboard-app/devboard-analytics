import logging
from uuid import UUID

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.http_client import get_http_client
from app.repositories.reports import get_sprint
from app.services.reports import get_burndown, get_velocity, get_who_did_what

logger = logging.getLogger(__name__)

async def _usernames(ids: list[str], authorization: str) -> dict[str, str]:
    """user_id -> username via devboard-core. On failure, returns {} so the chat still answers."""
    if not ids:
        return {}
    try:
        res = await get_http_client().post(
            f"{settings.DEVBOARD_CORE_URL}/api/users/batch/",
            json={"ids": ids},
            headers={"Authorization": authorization},
        )
        res.raise_for_status()
        return {u["user_id"]: u["username"] for u in res.json()}
    except (httpx.HTTPError, KeyError, ValueError):
        logger.warning("username lookup failed", exc_info=True)
        return {}

def make_tools(db: AsyncIOMotorDatabase, project_id: UUID, user_id: UUID, role: str, authorization: str):
    """Gemini-callable tools scoped to one project/user/role via closure.
    The LLM only ever supplies IDs it's given in context — it never sees
    or controls db access, actor scoping, or role checks."""

    async def who_did_what() -> dict:
        """Summarizes ticket activity per team member on this project.
        A non-lead only ever sees their own activity, regardless of what's asked.
        """
        actor = None if role == "lead" else user_id
        report = await get_who_did_what(project_id, db, actor=actor)
        data = report.model_dump(mode="json")
        names = await _usernames([a["actor"] for a in data["actors"]], authorization)
        for a in data["actors"]:
            a["username"] = names.get(a["actor"], "unknown member")
        return data

    async def velocity() -> dict:
        """Reports committed vs completed story points per sprint on this project.
        Lead-only — returns an error for non-leads.
        """
        if role != "lead":
            return {"error": "Only project leads can view velocity."}
        report = await get_velocity(project_id, db)
        return report.model_dump(mode="json")

    async def burndown(sprint_id: str) -> dict:
        """Reports remaining work per day of a sprint vs the ideal line.
        Lead-only — returns an error for non-leads.

        Args:
            sprint_id: UUID of the sprint (must belong to this project).
        """
        sprint = await get_sprint(UUID(sprint_id), db)
        if sprint is None or sprint.project_id != project_id:
            return {"error": "Sprint not found on this project."}
        if role != "lead":
            return {"error": "Only project leads can view burndown."}
        report = await get_burndown(sprint, db)
        return report.model_dump(mode="json")

    return [who_did_what, velocity, burndown]