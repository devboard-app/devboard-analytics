from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import AnyHttpUrl

from app.chat.tools import make_tools
from app.config import settings
from app.database import get_database
from app.dependencies import get_project_role
from app.exceptions import ForbiddenException, ServiceUnavailableException
from app.mcp_server.auth import JWTTokenVerifier

INSTRUCTIONS = """DevBoard project analytics: velocity, sprint burndown, team activity.
Always call a tool before stating numbers. Use velocity() to find sprint IDs for burndown().
Contributors only see their own activity; velocity and burndown are lead-only.
Refer to people by username, never show UUIDs."""

mcp = MCPServer(
    "DevBoard Analytics",
    instructions=INSTRUCTIONS,
    token_verifier=JWTTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(settings.DEVBOARD_CORE_URL),
        resource_server_url=AnyHttpUrl(settings.MCP_RESOURCE_URL),
        validate_token_resource=False,
    ),
)


async def _project_tools(project_id: UUID) -> dict:
    """Same scoping as POST /projects/{id}/chat/: membership check, then closure-bound tools."""
    token = get_access_token()
    if token is None or token.subject is None:
        raise ToolError("Not authenticated.")
    user_id = UUID(token.subject)
    try:
        role = await get_project_role(user_id, project_id)
    except ForbiddenException:
        raise ToolError("You are not a member of this project.")
    except ServiceUnavailableException:
        raise ToolError("Membership check is unavailable, try again shortly.")
    tools = make_tools(get_database(), project_id, user_id, role, f"Bearer {token.token}")
    return {t.__name__: t for t in tools}


@mcp.tool()
async def who_did_what(project_id: UUID) -> dict:
    """Ticket activity per team member. Non-leads only see their own activity."""
    return await (await _project_tools(project_id))["who_did_what"]()


@mcp.tool()
async def velocity(project_id: UUID) -> dict:
    """Committed vs completed story points per sprint. Lead-only."""
    return await (await _project_tools(project_id))["velocity"]()


@mcp.tool()
async def burndown(project_id: UUID, sprint_id: str) -> dict:
    """Remaining work per day of a sprint vs the ideal line. Lead-only."""
    return await (await _project_tools(project_id))["burndown"](sprint_id)