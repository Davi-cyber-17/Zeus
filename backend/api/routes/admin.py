"""
Zeus AI - Painel administrativo (API)
==========================================
Rotas restritas a administradores: visão geral do sistema, gestão de
usuários e listagem de plugins ativos. O frontend do painel admin
consome estes endpoints para exibir métricas e controles.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import get_current_admin
from backend.db import models
from backend.db.database import get_db
from backend.plugins.manager import get_plugin_manager

router = APIRouter(prefix="/api/admin", tags=["Administração"])


@router.get("/stats")
def get_stats(admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return {
        "total_users": db.query(models.User).count(),
        "total_conversations": db.query(models.Conversation).count(),
        "total_messages": db.query(models.Message).count(),
        "total_documents": db.query(models.Document).count(),
        "total_notes": db.query(models.Note).count(),
    }


@router.get("/users")
def list_users(admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return [
        {"id": u.id, "username": u.username, "email": u.email, "is_admin": u.is_admin, "is_active": u.is_active}
        for u in users
    ]


@router.patch("/users/{user_id}/toggle-active")
def toggle_user_active(user_id: str, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.is_active = not user.is_active
        db.commit()
    return {"id": user_id, "is_active": user.is_active if user else None}


@router.get("/action-history")
def get_action_history(admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    entries = db.query(models.ActionHistory).order_by(models.ActionHistory.created_at.desc()).limit(200).all()
    return [
        {
            "user_id": e.user_id,
            "action_type": e.action_type,
            "description": e.description,
            "status": e.status,
            "created_at": e.created_at,
        }
        for e in entries
    ]
