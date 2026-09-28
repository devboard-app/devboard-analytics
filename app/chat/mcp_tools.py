import json
from uuid import UUID

from mcp import Client


def make_mcp_tools(client: Client, project_id: UUID):
    """Gemini-callable tools that proxy to this service's MCP server (app/mcp_server).
    project_id is pinned here, not exposed to the LLM, so it can't query another project.
    Role and membership checks run on the MCP server, per call, from the forwarded JWT."""
    pid = str(project_id)

    async def _call(name: str, **args) -> dict:
        result = await client.call_tool(name, {"project_id": pid, **args})
        text = " ".join(block.text for block in result.content if block.type == "text")
        if result.is_error:
            return {"error": text}
        if result.structured_content is not None:
            return result.structured_content
        return json.loads(text)

    async def who_did_what() -> dict:
        """Summarizes ticket activity per team member on this project.
        A non-lead only ever sees their own activity, regardless of what's asked.
        """
        return await _call("who_did_what")

    async def velocity() -> dict:
        """Reports committed vs completed story points per sprint on this project.
        Lead-only — returns an error for non-leads.
        """
        return await _call("velocity")

    async def burndown(sprint_id: str) -> dict:
        """Reports remaining work per day of a sprint vs the ideal line.
        Lead-only — returns an error for non-leads.

        Args:
            sprint_id: UUID of the sprint (must belong to this project).
        """
        return await _call("burndown", sprint_id=sprint_id)

    return [who_did_what, velocity, burndown]
