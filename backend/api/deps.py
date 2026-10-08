"""
Zeus AI - Dependências compartilhadas da API
================================================
Funções reutilizadas pelas rotas via `Depends()` do FastAPI: obtenção
do usuário autenticado a partir do token JWT, e verificação de
permissão de administrador para o painel administrativo.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.core.security import decode_token
from backend.db import models
from backend.db.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou expiradas.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    decoded = decode_token(token, expected_type="access")
    if decoded is None:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == decoded.user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception

    # Se a senha foi trocada ou as sessões foram revogadas depois que este
    # token foi emitido, o número de versão não bate mais e o token é
    # considerado inválido — mesmo que ainda não tenha expirado.
    if decoded.token_version != user.token_version:
        raise credentials_exception

    return user


def get_current_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores.")
    return user
