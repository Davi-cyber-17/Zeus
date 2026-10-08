"""Plugin de exemplo: responde perguntas sobre data e hora atual."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.core.config import get_settings
from backend.core.logging_config import get_logger
from backend.plugins.base_plugin import ZeusPlugin

logger = get_logger("plugins.datetime")
settings = get_settings()

_PATTERN = re.compile(r"\b(que horas são|data de hoje|dia é hoje|current time|today.?s date)\b", re.I)


def _current_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("TIMEZONE '%s' inválido; usando UTC.", settings.TIMEZONE)
        return ZoneInfo("UTC")


class DateTimePlugin(ZeusPlugin):
    name = "datetime"
    description = "Responde perguntas sobre a data e a hora atuais (no fuso configurado em TIMEZONE)."

    def can_handle(self, user_message: str) -> bool:
        return bool(_PATTERN.search(user_message))

    def execute(self, user_message: str, context: dict[str, Any]) -> str:
        now = datetime.now(_current_timezone())
        return f"Agora são {now.strftime('%H:%M')} de {now.strftime('%d/%m/%Y')} ({settings.TIMEZONE})."
