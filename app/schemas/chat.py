from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    project_name: str | None = None


class ChatResponse(BaseModel):
    answer: str