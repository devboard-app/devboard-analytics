import logging

from google import genai
from google.genai import errors, types

from app.config import settings
from app.exceptions import ServiceUnavailableException

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.GEMINI_API_KEY,
                       http_options=types.HttpOptions(timeout=20_000, retry_options=types.HttpRetryOptions(attempts=2)))

MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]

async def ask(message: str, tools: list, project_name: str | None = None, role: str = "contributor") -> str:
    label = project_name or "this project"
    access = (
        "The user is a project lead: they can see velocity, burndown and everyone's activity."
        if role == "lead" else
        "The user is a contributor: they can only see their own activity. Velocity and burndown "
        "are for project leads. If asked for them, say so in one sentence and offer to summarize "
        "the user's own activity instead."
    )
    system_instruction = f"""You are the DevBoard assistant for the project "{label}".

    You can answer these, and must call a tool first (never guess numbers):
    - Velocity: committed vs completed story points per sprint -> velocity()
    - Sprint progress or burndown -> velocity() to find the sprint, then burndown(sprint_id)
    - Who worked on what, team activity -> who_did_what()
    - "How is the project going" or "current state" -> combine the tools into a short status summary

    {access}

    Rules:
    - Refer to the project and people by name. Never show UUIDs.
    - Answer in GitHub-flavored Markdown: ## headings for sections, lists, **bold** key numbers,
    tables to compare sprints or members. A one-line answer stays a single plain sentence.
    - If a tool returns no data, say what is missing (for example "no completed sprints yet").
    - Refuse only questions clearly unrelated to this project (general coding help, writing code,
    trivia, other projects). For those, reply with exactly this sentence and nothing else:
    I can only answer questions about {label}'s sprints, velocity and team activity. Try: "How did the last sprint go?"
    """
    for model in MODELS:
        chat = _client.aio.chats.create(
            model=model,
            config={"tools": tools, "system_instruction": system_instruction},
        )
        try:
            response = await chat.send_message(message)
        except errors.ServerError:  # 5xx: model overloaded or down
            logger.warning("Gemini %s unavailable, trying next model", model)
            continue
        except errors.ClientError as exc:  # 4xx: only 429 (rate limit) is worth a retry
            if exc.code != 429:
                raise
            logger.warning("Gemini %s rate-limited, trying next model", model)
            continue
        return response.text or "I couldn't generate a response - try rephrasing your question."
    raise ServiceUnavailableException("Assistant")  # all models failed -> 503 "Assistant unavailable."