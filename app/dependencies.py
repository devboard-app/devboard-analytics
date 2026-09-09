import logging
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends, Header
from jose import JWTError, jwt

from app.config import settings
from app.exceptions import (
    ForbiddenException,
    ServiceUnavailableException,
    UnauthorizedException,
)
from app.http_client import get_http_client

logger = logging.getLogger(__name__)

async def verify_internal_key(x_service_key: Annotated[str, Header(...)]):
    if x_service_key != settings.INTERNAL_API_KEY:
        raise ForbiddenException

async def get_current_user_id(authorization: Annotated[str | None, Header(...)] = None) -> UUID:
    if authorization is None or not authorization.startswith("Bearer "):
        raise UnauthorizedException
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise UnauthorizedException 

async def get_project_role(user_id: UUID, project_id: UUID) -> str:
    try:
        response = await get_http_client().get(
            f"{settings.DEVBOARD_WORK_URL}/api/internal/projects/{project_id}/members/{user_id}/",
            headers={"X-Service-Key": settings.INTERNAL_API_KEY},
        )
    except httpx.TransportError:
        logger.warning("devboard-work service is unavailable", exc_info=True)
        raise ServiceUnavailableException("Authorization service")

    if response.status_code >= 500:
        logger.error(f"Membership check returned {response.status_code}")
        raise ServiceUnavailableException("Authorization service")

    if response.status_code != 200:
        raise ForbiddenException
    
    return response.json()["role"]


async def require_project_member(project_id: UUID, user_id: Annotated[UUID, Depends(get_current_user_id)]) -> str:
    return await get_project_role(user_id, project_id)

async def require_project_lead(project_id: UUID, user_id: Annotated[UUID, Depends(get_current_user_id)]) -> str:
    role = await get_project_role(user_id, project_id)
    if role != "lead":
        raise ForbiddenException
    return role
