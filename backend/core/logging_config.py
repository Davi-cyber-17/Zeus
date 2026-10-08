"""
Zeus AI - Logging estruturado
==============================
Configura logs em console (colorido, para desenvolvimento) e em arquivo
rotativo (para auditoria e histórico de atividades), conforme exigido
pelo requisito de "registro de eventos e atividades".
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.core.config import get_settings

settings = get_settings()

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """Configura o logger raiz do Zeus. Chamado uma vez, na inicialização."""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    root_logger = logging.getLogger("zeus")
    root_logger.setLevel(settings.LOG_LEVEL)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        log_dir / "zeus.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Log específico de eventos/ações do usuário (auditoria)
    activity_logger = logging.getLogger("zeus.activity")
    activity_handler = RotatingFileHandler(
        log_dir / "activity.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    activity_handler.setFormatter(formatter)
    activity_logger.addHandler(activity_handler)
    activity_logger.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"zeus.{name}")


def log_activity(user_id: str, action: str, details: str = "") -> None:
    """Registra uma ação do usuário no log de auditoria/atividades."""
    logging.getLogger("zeus.activity").info(
        "user=%s | action=%s | details=%s", user_id, action, details
    )
