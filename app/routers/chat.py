from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.chat.gemini_client import ask
from app.chat.tools import make_tools
from app.database import get_database
from app.dependencies import get_current_user_id, require_project_member
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(project_id: UUID, body: ChatRequest, db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
                user_id: Annotated[UUID, Depends(get_current_user_id)], role: Annotated[str, Depends(require_project_member)], authorization: Annotated[str, Header()]) -> ChatResponse:
    tools = make_tools(db, project_id, user_id, role, authorization)
    answer = await ask(body.message, tools, project_name=body.project_name, role=role)
    return ChatResponse(answer=answer)