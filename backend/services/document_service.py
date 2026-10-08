"""
Zeus AI - Leitura e análise de documentos
==============================================
Extrai texto de documentos enviados (PDF, TXT, DOCX). O texto completo
é guardado no SQLite (Document.content), permitindo que o usuário faça
perguntas sobre o conteúdo de seus próprios arquivos via busca por
palavra-chave — sem nenhuma indexação vetorial ou serviço externo.
"""
from __future__ import annotations

from pathlib import Path

from backend.core.logging_config import get_logger

logger = get_logger("services.documents")

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


def extract_text(file_path: str) -> str:
    """Extrai texto bruto de um documento, de acordo com sua extensão."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:  # noqa: BLE001
            logger.error("Falha ao extrair texto de PDF: %s", exc)
            return ""

    if suffix == ".docx":
        try:
            import docx

            document = docx.Document(str(path))
            return "\n".join(p.text for p in document.paragraphs)
        except Exception as exc:  # noqa: BLE001
            logger.error("Falha ao extrair texto de DOCX: %s", exc)
            return ""

    logger.warning("Extensão não suportada para extração: %s", suffix)
    return ""


def summarize_document(text: str, max_chars: int = 500) -> str:
    """Gera um resumo simples (heurístico) do documento.
    Para resumos de alta qualidade, o texto completo é enviado ao
    ZeusBrain (LLM) a partir da rota de documentos."""
    cleaned = " ".join(text.split())
    return cleaned[:max_chars] + ("..." if len(cleaned) > max_chars else "")
