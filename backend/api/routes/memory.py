"""Zeus AI - Rotas de memória: anotações, preferências e busca semântica."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.security import decrypt_data
from backend.db import models
from backend.db.database import get_db
from backend.memory.memory_manager import MemoryManager
from backend.schemas.memory import (
    NoteCreate,
    NoteOut,
    PreferenceSet,
    SearchQuery,
    SearchResultItem,
)

router = APIRouter(prefix="/api/memory", tags=["Memória"])


@router.post("/notes", response_model=NoteOut)
def create_note(payload: NoteCreate, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    memory = MemoryManager(db)
    return memory.save_note(user.id, payload.title, payload.content, payload.tags)


@router.get("/notes")
def list_notes(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    notes = db.query(models.Note).filter(models.Note.user_id == user.id).order_by(models.Note.updated_at.desc()).all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "content": decrypt_data(n.content_encrypted),
            "tags": n.tags,
            "updated_at": n.updated_at,
        }
        for n in notes
    ]


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    note = db.query(models.Note).filter(models.Note.id == note_id, models.Note.user_id == user.id).first()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anotação não encontrada.")
    db.delete(note)
    db.commit()


@router.post("/preferences")
def set_preference(payload: PreferenceSet, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    memory = MemoryManager(db)
    pref = memory.set_preference(user.id, payload.key, payload.value)
    return {"key": pref.key, "value": pref.value}


@router.get("/preferences")
def get_preferences(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    memory = MemoryManager(db)
    return memory.get_preferences(user.id)


@router.post("/search", response_model=list[SearchResultItem])
def semantic_search(payload: SearchQuery, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    memory = MemoryManager(db)
    return memory.semantic_search(user.id, payload.query, payload.top_k)
