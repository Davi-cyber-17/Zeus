"""Schemas Pydantic para lembretes."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReminderCreate(BaseModel):
    content: str
    remind_at: Optional[datetime] = None


class ReminderOut(BaseModel):
    id: str
    content: str
    remind_at: Optional[datetime] = None
    done: bool
    created_at: datetime

    class Config:
        from_attributes = True
