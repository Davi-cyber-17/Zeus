"""Zeus AI - Rotas de lembretes (criados manualmente ou via chat)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.db import models
from backend.db.database import get_db
from backend.schemas.reminders import ReminderCreate, ReminderOut

router = APIRouter(prefix="/api/reminders", tags=["Lembretes"])


@router.post("", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: ReminderCreate, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    reminder = models.Reminder(user_id=user.id, content=payload.content, remind_at=payload.remind_at)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.get("", response_model=list[ReminderOut])
def list_reminders(
    include_done: bool = False,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.Reminder).filter(models.Reminder.user_id == user.id)
    if not include_done:
        query = query.filter(models.Reminder.done.is_(False))
    return query.order_by(models.Reminder.created_at.desc()).all()


@router.patch("/{reminder_id}/done", response_model=ReminderOut)
def mark_reminder_done(
    reminder_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    reminder = (
        db.query(models.Reminder)
        .filter(models.Reminder.id == reminder_id, models.Reminder.user_id == user.id)
        .first()
    )
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lembrete não encontrado.")
    reminder.done = True
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(reminder_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    reminder = (
        db.query(models.Reminder)
        .filter(models.Reminder.id == reminder_id, models.Reminder.user_id == user.id)
        .first()
    )
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lembrete não encontrado.")
    db.delete(reminder)
    db.commit()
