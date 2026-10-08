"""Schemas Pydantic para o chat/conversas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    language: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    source: str  # "llm" | "plugin"


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime

    class Config:
        from_attributes = True
