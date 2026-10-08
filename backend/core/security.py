"""
Zeus AI - Segurança
====================
Concentra toda a lógica sensível: hashing de senha, emissão/validação
de tokens JWT (acesso + refresh) e criptografia simétrica de dados
armazenados (usada para proteger anotações, documentos e preferências
no banco de dados).
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh"]


# ---------------------------------------------------------------------
# Senhas
# ---------------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------
# JWT — tokens de acesso (curta duração) e refresh (longa duração)
# ---------------------------------------------------------------------
@dataclass
class DecodedToken:
    user_id: str
    token_version: int
    token_type: TokenType


def _create_token(subject: str, token_version: int, token_type: TokenType, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": subject,
        "ver": token_version,
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, token_version: int = 0) -> str:
    return _create_token(
        subject,
        token_version,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str, token_version: int = 0) -> str:
    return _create_token(
        subject,
        token_version,
        "refresh",
        timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
    )


def decode_token(token: str, expected_type: Optional[TokenType] = None) -> Optional[DecodedToken]:
    """Decodifica e valida um JWT. Retorna None se inválido, expirado ou
    do tipo errado (ex.: usar um refresh token onde um access token era
    esperado, e vice-versa)."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

    token_type: str = payload.get("type", "access")
    if expected_type is not None and token_type != expected_type:
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    return DecodedToken(user_id=user_id, token_version=payload.get("ver", 0), token_type=token_type)


def decode_access_token(token: str) -> Optional[str]:
    """Mantido por compatibilidade: retorna apenas o user_id de um access token."""
    decoded = decode_token(token, expected_type="access")
    return decoded.user_id if decoded else None


# ---------------------------------------------------------------------
# Criptografia simétrica de dados em repouso (Fernet / AES-128)
# ---------------------------------------------------------------------
def _get_fernet() -> Fernet:
    # Deriva uma chave Fernet válida a partir da SECRET_KEY do sistema.
    import base64
    import hashlib

    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_data(plaintext: str) -> str:
    """Criptografa dados sensíveis antes de persistir no banco."""
    if not plaintext:
        return plaintext
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_data(ciphertext: str) -> str:
    """Descriptografa dados lidos do banco."""
    if not ciphertext:
        return ciphertext
    return _get_fernet().decrypt(ciphertext.encode()).decode()
