"""
Zeus AI - Rate limiting simples (em memória)
================================================
Proteção básica contra força bruta em endpoints sensíveis (login,
registro). Implementado com uma janela deslizante em memória — sem
Redis nem nenhum serviço externo, seguindo o princípio "100% local"
do Zeus.

Observação: como é em memória, cada worker/processo tem seu próprio
contador. Para uma instância pessoal (um único processo `uvicorn`),
isso já é suficiente. Em produção com múltiplos workers, prefira um
backend compartilhado (ex.: Redis).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from backend.core.config import get_settings

settings = get_settings()

_lock = threading.Lock()
_attempts: dict[str, list[float]] = defaultdict(list)


def _client_key(request: Request, extra: str = "") -> str:
    client_ip = request.client.host if request.client else "unknown"
    return f"{client_ip}:{extra}"


def check_rate_limit(
    request: Request,
    bucket: str,
    max_attempts: int | None = None,
    window_seconds: int | None = None,
    extra_key: str = "",
) -> None:
    """Lança HTTP 429 se o número de tentativas recentes para essa chave
    (IP + rótulo do bucket + chave extra, ex.: username) exceder o limite
    permitido dentro da janela de tempo configurada."""
    if not settings.RATE_LIMIT_ENABLED:
        return

    max_attempts = max_attempts or settings.LOGIN_RATE_LIMIT_ATTEMPTS
    window_seconds = window_seconds or settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS

    key = f"{bucket}:{_client_key(request, extra_key)}"
    now = time.monotonic()

    with _lock:
        timestamps = [t for t in _attempts[key] if now - t < window_seconds]
        if len(timestamps) >= max_attempts:
            _attempts[key] = timestamps
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas. Aguarde um instante antes de tentar novamente.",
            )
        timestamps.append(now)
        _attempts[key] = timestamps


def reset_rate_limit(request: Request, bucket: str, extra_key: str = "") -> None:
    """Limpa o contador (ex.: após um login bem-sucedido)."""
    key = f"{bucket}:{_client_key(request, extra_key)}"
    with _lock:
        _attempts.pop(key, None)
