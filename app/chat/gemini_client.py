from google import genai

from app.config import settings

_client = genai.Client(api_key=settings.GEMINI_API_KEY)


async def ask(message: str, tools: list, project_name: str | None = None) -> str:
    label = project_name or "this project"
    system_instruction = (
        f"You are answering questions about the DevBoard project '{label}'. "
        "Refer to it by name. Never show raw UUIDs (project, sprint, or user ids) "
        "in your answer — use names where available, or a short description otherwise."
    )
    chat = _client.aio.chats.create(
        model="gemini-3.5-flash-lite",
        config={"tools": tools, "system_instruction": system_instruction},
    )
    response = await chat.send_message(message)
    return response.text or "I couldn't generate a response — try rephrasing your question."