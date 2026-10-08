"""
Plugin de exemplo: cria e lista lembretes simples via linguagem natural.
Demonstra um plugin com estado persistente (usa a sessão de banco de
dados repassada no contexto da mensagem) e ainda sem depender de
nenhum serviço externo — os lembretes ficam salvos no próprio SQLite.
"""
from __future__ import annotations

import re
from typing import Any

from backend.core.logging_config import get_logger
from backend.plugins.base_plugin import ZeusPlugin

logger = get_logger("plugins.reminder")

_CREATE_PATTERN = re.compile(
    r"(?:lembre-me|lembra|me lembre|lembrar)\s+de\s+(.+)", re.I
)
_LIST_PATTERN = re.compile(
    r"\b(meus? lembretes?|minhas? lembran[cç]as?|minhas? tarefas?)\b", re.I
)


class ReminderPlugin(ZeusPlugin):
    name = "reminder"
    description = "Cria e lista lembretes simples (ex.: 'lembre-me de pagar a conta')."

    def can_handle(self, user_message: str) -> bool:
        return bool(_CREATE_PATTERN.search(user_message) or _LIST_PATTERN.search(user_message))

    def execute(self, user_message: str, context: dict[str, Any]) -> str:
        db = context.get("db")
        user_id = context.get("user_id")
        if db is None or user_id is None:
            return "Não consegui acessar a memória para lidar com lembretes agora."

        from backend.db import models

        list_match = _LIST_PATTERN.search(user_message)
        if list_match:
            pending = (
                db.query(models.Reminder)
                .filter(models.Reminder.user_id == user_id, models.Reminder.done.is_(False))
                .order_by(models.Reminder.created_at.desc())
                .all()
            )
            if not pending:
                return "Você não tem lembretes pendentes no momento."
            items = "\n".join(f"- {r.content}" for r in pending)
            return f"Seus lembretes pendentes:\n{items}"

        create_match = _CREATE_PATTERN.search(user_message)
        if create_match:
            content = create_match.group(1).strip().rstrip(".")
            if not content:
                return "O que você gostaria que eu lembrasse?"
            reminder = models.Reminder(user_id=user_id, content=content)
            db.add(reminder)
            db.commit()
            logger.info("Lembrete criado para o usuário %s.", user_id)
            return f'Combinado, vou lembrar: "{content}".'

        return "Não entendi o lembrete. Tente algo como 'lembre-me de comprar leite'."
