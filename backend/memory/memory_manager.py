"""
Zeus AI - Gerenciador de memória inteligente
================================================
Camada de mais alto nível que combina o banco relacional (fonte de
verdade estruturada) com uma busca por palavra-chave 100% local
(SQL/Python, sem nenhuma dependência externa), oferecendo uma API
única para o restante do sistema armazenar e recuperar contexto:
conversas, documentos, anotações e preferências.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.core.logging_config import get_logger
from backend.db import models

logger = get_logger("memory.manager")

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _keywords(text: str) -> list[str]:
    """Extrai palavras-chave relevantes (>=3 caracteres) de uma consulta."""
    return [w for w in _WORD_RE.findall(text.lower()) if len(w) >= 3]


class MemoryManager:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Conversas / mensagens
    # ------------------------------------------------------------------
    def save_message(self, conversation_id: str, user_id: str, role: str, content: str) -> models.Message:
        message = models.Message(conversation_id=conversation_id, role=role, content=content)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_conversation_history(self, conversation_id: str, limit: int = 20) -> list[models.Message]:
        return (
            self.db.query(models.Message)
            .filter(models.Message.conversation_id == conversation_id)
            .order_by(models.Message.created_at.desc())
            .limit(limit)
            .all()[::-1]
        )

    # ------------------------------------------------------------------
    # Anotações
    # ------------------------------------------------------------------
    def save_note(self, user_id: str, title: str, content: str, tags: str | None = None) -> models.Note:
        from backend.core.security import encrypt_data

        note = models.Note(
            user_id=user_id, title=title, content_encrypted=encrypt_data(content), tags=tags
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    # ------------------------------------------------------------------
    # Preferências (aprendizado do usuário)
    # ------------------------------------------------------------------
    def set_preference(self, user_id: str, key: str, value: str, learned_automatically: bool = False) -> models.Preference:
        pref = (
            self.db.query(models.Preference)
            .filter(models.Preference.user_id == user_id, models.Preference.key == key)
            .first()
        )
        if pref:
            pref.value = value
            pref.learned_automatically = learned_automatically
        else:
            pref = models.Preference(
                user_id=user_id, key=key, value=value, learned_automatically=learned_automatically
            )
            self.db.add(pref)
        self.db.commit()
        self.db.refresh(pref)
        return pref

    def get_preferences(self, user_id: str) -> dict[str, str]:
        prefs = self.db.query(models.Preference).filter(models.Preference.user_id == user_id).all()
        return {p.key: p.value for p in prefs}

    # ------------------------------------------------------------------
    # Histórico de ações (auditoria/produtividade)
    # ------------------------------------------------------------------
    def log_action(self, user_id: str, action_type: str, description: str, status: str = "success") -> None:
        entry = models.ActionHistory(
            user_id=user_id, action_type=action_type, description=description, status=status
        )
        self.db.add(entry)
        self.db.commit()

    # ------------------------------------------------------------------
    # Busca por palavra-chave unificada (contexto para o LLM)
    # ------------------------------------------------------------------
    def semantic_search(self, user_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Busca por palavra-chave em mensagens, documentos e anotações do
        usuário — 100% SQL/Python, sem nenhum serviço ou modelo externo."""
        words = _keywords(query)
        if not words:
            return []

        results: list[dict[str, Any]] = []

        # --- Mensagens ---------------------------------------------------
        msg_filters = or_(*[models.Message.content.ilike(f"%{w}%") for w in words])
        messages = (
            self.db.query(models.Message)
            .join(models.Conversation)
            .filter(models.Conversation.user_id == user_id, msg_filters)
            .order_by(models.Message.created_at.desc())
            .limit(top_k)
            .all()
        )
        for m in messages:
            results.append(
                {
                    "id": f"msg_{m.id}",
                    "text": m.content,
                    "metadata": {"type": "message", "role": m.role, "conversation_id": m.conversation_id},
                }
            )

        # --- Documentos ----------------------------------------------------
        doc_filters = or_(*[models.Document.content.ilike(f"%{w}%") for w in words])
        documents = (
            self.db.query(models.Document)
            .filter(models.Document.user_id == user_id, models.Document.content.isnot(None), doc_filters)
            .order_by(models.Document.created_at.desc())
            .limit(top_k)
            .all()
        )
        for d in documents:
            snippet = _best_snippet(d.content or "", words)
            results.append(
                {
                    "id": f"doc_{d.id}",
                    "text": snippet,
                    "metadata": {"type": "document", "filename": d.filename, "document_id": d.id},
                }
            )

        # --- Anotações (conteúdo fica criptografado no banco, então o
        #     filtro por palavra-chave é feito em Python após decifrar) ---
        from backend.core.security import decrypt_data

        notes = self.db.query(models.Note).filter(models.Note.user_id == user_id).all()
        for n in notes:
            content = decrypt_data(n.content_encrypted)
            haystack = f"{n.title}\n{content}".lower()
            if any(w in haystack for w in words):
                results.append(
                    {
                        "id": f"note_{n.id}",
                        "text": f"{n.title}\n{content}",
                        "metadata": {"type": "note", "title": n.title},
                    }
                )

        return results[:top_k]

    def build_context_for_prompt(self, user_id: str, query: str, top_k: int = 5) -> str:
        """Monta um bloco de contexto relevante para enriquecer o prompt do LLM."""
        results = self.semantic_search(user_id=user_id, query=query, top_k=top_k)
        if not results:
            return ""
        lines = ["Contexto relevante da memória do usuário:"]
        for item in results:
            lines.append(f"- [{item['metadata'].get('type', 'memória')}] {item['text'][:300]}")
        return "\n".join(lines)


def _best_snippet(text: str, words: list[str], radius: int = 150) -> str:
    """Retorna um trecho do texto ao redor da primeira palavra-chave encontrada."""
    lowered = text.lower()
    for w in words:
        idx = lowered.find(w)
        if idx != -1:
            start = max(0, idx - radius)
            end = min(len(text), idx + radius)
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(text) else ""
            return f"{prefix}{text[start:end]}{suffix}"
    return text[: radius * 2]
