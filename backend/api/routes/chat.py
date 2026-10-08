"""
Zeus AI - Rotas de chat
==========================
Coração da interação: recebe a mensagem do usuário, tenta rotear para
um plugin, e se nenhum plugin tratar, aciona o LLM com contexto de
memória (RAG). A fala da resposta (texto-para-voz) é feita 100% no
navegador via Web Speech API — o backend só devolve texto.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.logging_config import get_logger
from backend.db import models
from backend.db.database import SessionLocal, get_db
from backend.memory.memory_manager import MemoryManager
from backend.plugins.manager import get_plugin_manager
from backend.schemas.chat import ChatRequest, ChatResponse, ConversationOut, MessageOut
from backend.services.llm_service import get_brain

router = APIRouter(prefix="/api/chat", tags=["Chat"])
logger = get_logger("api.chat")


def _get_or_create_conversation(db: Session, user: models.User, conversation_id: str | None) -> models.Conversation:
    if conversation_id:
        conv = (
            db.query(models.Conversation)
            .filter(models.Conversation.id == conversation_id, models.Conversation.user_id == user.id)
            .first()
        )
        if conv:
            return conv
    conv = models.Conversation(user_id=user.id, title="Nova conversa")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def _get_owned_conversation(db: Session, user: models.User, conversation_id: str) -> models.Conversation:
    """Busca uma conversa garantindo que ela pertence ao usuário autenticado.
    Lança 404 tanto para conversas inexistentes quanto para conversas de
    outro usuário — assim não revelamos se o ID existe ou não."""
    conv = (
        db.query(models.Conversation)
        .filter(models.Conversation.id == conversation_id, models.Conversation.user_id == user.id)
        .first()
    )
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
    return conv


def _build_history(memory: MemoryManager, conversation_id: str) -> list[dict[str, str]]:
    return [
        {"role": m.role, "content": m.content}
        for m in memory.get_conversation_history(conversation_id, limit=10)
        if m.role in ("user", "assistant")
    ][:-1]  # remove a última (a que acabamos de salvar) para não duplicar


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    memory = MemoryManager(db)
    conversation = _get_or_create_conversation(db, user, payload.conversation_id)

    # 1. Salva a mensagem do usuário (e indexa na memória semântica).
    memory.save_message(conversation.id, user.id, "user", payload.message)

    # 2. Tenta rotear para um plugin antes de acionar o LLM (mais rápido
    #    e determinístico para tarefas específicas, ex.: hora, clima,
    #    lembretes). O plugin recebe a sessão de banco para poder ler/
    #    gravar seu próprio estado (ex.: o plugin de lembretes).
    plugin_manager = get_plugin_manager()
    plugin_response = plugin_manager.route(
        payload.message, context={"user_id": user.id, "language": payload.language, "db": db}
    )

    if plugin_response is not None:
        reply = plugin_response
        source = "plugin"
    else:
        # 3. Monta contexto de memória (RAG) e histórico recente da conversa.
        memory_context = memory.build_context_for_prompt(user.id, payload.message)
        history = _build_history(memory, conversation.id)

        brain = get_brain()
        reply = brain.think(
            user_message=payload.message,
            history=history,
            memory_context=memory_context,
            language=payload.language,
        )
        source = "llm"

    # 4. Salva a resposta do Zeus.
    memory.save_message(conversation.id, user.id, "assistant", reply)
    memory.log_action(user.id, "chat", f"Mensagem processada (fonte: {source}).")

    return ChatResponse(
        conversation_id=conversation.id,
        reply=reply,
        source=source,
    )


@router.post("/stream")
def chat_stream(
    payload: ChatRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Mesma lógica do endpoint de chat normal, mas devolve a resposta do
    LLM como Server-Sent Events (SSE), token a token, para o frontend
    poder mostrar o efeito de digitação em tempo real. Respostas de
    plugin não streamam (são instantâneas por natureza) — chegam de uma
    vez só no primeiro evento."""
    memory = MemoryManager(db)
    conversation = _get_or_create_conversation(db, user, payload.conversation_id)
    memory.save_message(conversation.id, user.id, "user", payload.message)

    plugin_manager = get_plugin_manager()
    plugin_response = plugin_manager.route(
        payload.message, context={"user_id": user.id, "language": payload.language, "db": db}
    )

    conversation_id = conversation.id
    user_id = user.id
    message = payload.message
    language = payload.language

    def event_stream():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        yield sse("start", {"conversation_id": conversation_id})

        # Cada geração roda numa sessão de banco própria, já que o generator
        # continua executando depois que a dependência `db` da rota (escopo
        # de request) poderia ter sido fechada pelo FastAPI.
        stream_db = SessionLocal()
        try:
            stream_memory = MemoryManager(stream_db)
            full_reply = ""
            source = "plugin"

            if plugin_response is not None:
                full_reply = plugin_response
                yield sse("chunk", {"text": full_reply})
            else:
                source = "llm"
                memory_context = stream_memory.build_context_for_prompt(user_id, message)
                history = _build_history(stream_memory, conversation_id)
                brain = get_brain()
                for chunk in brain.think_stream(
                    user_message=message,
                    history=history,
                    memory_context=memory_context,
                    language=language,
                ):
                    full_reply += chunk
                    yield sse("chunk", {"text": chunk})

            stream_memory.save_message(conversation_id, user_id, "assistant", full_reply)
            stream_memory.log_action(user_id, "chat", f"Mensagem processada (fonte: {source}).")
            yield sse("done", {"source": source})
        except Exception as exc:  # noqa: BLE001
            logger.error("Erro durante streaming de chat: %s", exc)
            yield sse("error", {"detail": "Ocorreu um erro ao gerar a resposta."})
        finally:
            stream_db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.Conversation)
        .filter(models.Conversation.user_id == user.id)
        .order_by(models.Conversation.created_at.desc())
        .all()
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(
    conversation_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    memory = MemoryManager(db)
    # Garante que a conversa pertence ao usuário autenticado antes de
    # devolver qualquer mensagem (evita acesso indevido às conversas de
    # outras pessoas — ver correção de segurança no changelog do Zeus).
    conversation = _get_owned_conversation(db, user, conversation_id)
    return memory.get_conversation_history(conversation.id, limit=200)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    conversation = _get_owned_conversation(db, user, conversation_id)
    db.delete(conversation)
    db.commit()
