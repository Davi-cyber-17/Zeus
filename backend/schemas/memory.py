"""Schemas Pydantic para memória: anotações, preferências e busca."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NoteCreate(BaseModel):
    title: str
    content: str
    tags: Optional[str] = None


class NoteOut(BaseModel):
    id: str
    title: str
    tags: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PreferenceSet(BaseModel):
    key: str
    value: str


class SearchQuery(BaseModel):
    query: str
    top_k: int = 5


class SearchResultItem(BaseModel):
    id: str
    text: str
    metadata: dict
