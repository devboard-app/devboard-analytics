from typing import Annotated
from uuid import UUID

import httpx2
from fastapi import APIRouter, Depends, Header
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app.chat.gemini_client import ask
from app.chat.mcp_tools import make_mcp_tools
from app.config import settings
from app.dependencies import require_project_member
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(project_id: UUID, body: ChatRequest, role: Annotated[str, Depends(require_project_member)],
                authorization: Annotated[str, Header()]) -> ChatResponse:
    # The user's JWT is forwarded so the MCP server applies the same per-user scoping.
    # role is still resolved here: it drives the system prompt, and 403s non-members early.
    async with (
        httpx2.AsyncClient(headers={"Authorization": authorization}, timeout=30.0) as http,
        Client(streamable_http_client(settings.MCP_INTERNAL_URL, http_client=http)) as mcp_client,
    ):
        tools = make_mcp_tools(mcp_client, project_id)
        answer = await ask(body.message, tools, project_name=body.project_name, role=role)
    return ChatResponse(answer=answer)
