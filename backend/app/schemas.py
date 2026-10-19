from datetime import datetime

from pydantic import BaseModel, Field


class Usage(BaseModel):
    model_used: str | None = None
    prompt_tokens: int = 0
    reply_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0


class ChatResponse(BaseModel):
    reply: str
    image_url: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    session_id: str
    usage: Usage | None = None


class SessionOut(BaseModel):
    session_id: str
    title: str
    timestamp: datetime


class HistoryItem(BaseModel):
    role: str
    text: str
    image: str | None = None
    images: list[str] = Field(default_factory=list)
    cost: float
    usage: Usage | None = None
