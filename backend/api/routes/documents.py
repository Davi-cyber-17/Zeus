"""
Zeus AI - Rotas de documentos
=================================
Upload, leitura e indexação de documentos (PDF, DOCX, TXT, MD),
permitindo que o Zeus responda perguntas sobre o conteúdo desses
arquivos. O texto completo é extraído e guardado no próprio SQLite,
possibilitando busca por palavra-chave sem nenhum serviço externo.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.config import get_settings
from backend.core.logging_config import get_logger
from backend.db import models
from backend.db.database import get_db
from backend.services.document_service import SUPPORTED_EXTENSIONS, extract_text, summarize_document

router = APIRouter(prefix="/api/documents", tags=["Documentos"])
logger = get_logger("api.documents")
settings = get_settings()

_DOCS_DIR = Path(settings.DOCS_DIR)
_DOCS_DIR.mkdir(parents=True, exist_ok=True)
_MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/upload")
async def upload_document(
    file: UploadFile, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    # `Path(...).name` descarta qualquer componente de diretório (ex.:
    # "../../etc/passwd" vira apenas "passwd"), evitando que um nome de
    # arquivo malicioso grave fora de DOCS_DIR (path traversal).
    safe_filename = Path(file.filename or "arquivo").name
    suffix = Path(safe_filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Formato não suportado: {suffix}")

    dest_path = _DOCS_DIR / f"{uuid.uuid4()}_{safe_filename}"

    size = 0
    try:
        with dest_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Arquivo maior que o limite de {settings.MAX_UPLOAD_SIZE_MB}MB.",
                    )
                buffer.write(chunk)
    except HTTPException:
        dest_path.unlink(missing_ok=True)
        raise

    text = extract_text(str(dest_path))
    summary = summarize_document(text) if text else None

    document = models.Document(
        user_id=user.id,
        filename=safe_filename,
        file_path=str(dest_path),
        content_type=file.content_type or "application/octet-stream",
        content=text or None,
        summary=summary,
        indexed=bool(text),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    if text:
        logger.info("Documento '%s' indexado com sucesso (busca por palavra-chave).", safe_filename)

    return {
        "id": document.id,
        "filename": document.filename,
        "summary": document.summary,
        "indexed": document.indexed,
    }


@router.get("")
def list_documents(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = db.query(models.Document).filter(models.Document.user_id == user.id).all()
    return [
        {"id": d.id, "filename": d.filename, "summary": d.summary, "indexed": d.indexed, "created_at": d.created_at}
        for d in docs
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.user_id == user.id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado.")

    Path(document.file_path).unlink(missing_ok=True)
    db.delete(document)
    db.commit()
