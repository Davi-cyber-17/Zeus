"""Zeus AI - Rotas de autenticação (registro, login, refresh, senha)."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.config import get_settings
from backend.core.logging_config import get_logger, log_activity
from backend.core.rate_limit import check_rate_limit, reset_rate_limit
from backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from backend.db import models
from backend.db.database import get_db
from backend.schemas.auth import ChangePassword, RefreshRequest, Token, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])
logger = get_logger("api.auth")
settings = get_settings()


def _issue_token_pair(user: models.User) -> Token:
    return Token(
        access_token=create_access_token(subject=user.id, token_version=user.token_version),
        refresh_token=create_refresh_token(subject=user.id, token_version=user.token_version),
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> models.User:
    # Registro também é limitado por IP para dificultar criação em massa de
    # contas (limite mais generoso que o login, já que é uma ação legítima
    # mais rara por usuário).
    check_rate_limit(
        request,
        bucket="register",
        max_attempts=settings.REGISTER_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.REGISTER_RATE_LIMIT_WINDOW_SECONDS,
    )

    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Nome de usuário já cadastrado.")
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    # O primeiro usuário cadastrado no sistema vira administrador automaticamente.
    is_first_user = db.query(models.User).count() == 0

    user = models.User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_admin=is_first_user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    reset_rate_limit(request, bucket="register")
    log_activity(user.id, "register", f"Usuário {user.username} criado.")
    logger.info("Novo usuário registrado: %s", user.username)
    return user


@router.post("/login", response_model=Token)
def login(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Token:
    # Limita tentativas por IP + nome de usuário, para não travar todo mundo
    # se um único usuário errar a senha várias vezes (e ainda dificultar
    # força bruta contra uma conta específica).
    check_rate_limit(request, bucket="login", extra_key=form_data.username)

    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Esta conta está desativada.")

    reset_rate_limit(request, bucket="login", extra_key=form_data.username)
    log_activity(user.id, "login", "Login realizado com sucesso.")
    return _issue_token_pair(user)


@router.post("/refresh", response_model=Token)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    """Troca um refresh token válido por um novo par de tokens, sem exigir
    login novamente. Evita que o usuário seja deslogado a cada 30 minutos
    (duração do access token)."""
    decoded = decode_token(payload.refresh_token, expected_type="refresh")
    if decoded is None:
        raise HTTPException(status_code=401, detail="Refresh token inválido ou expirado.")

    user = db.query(models.User).filter(models.User.id == decoded.user_id).first()
    if user is None or not user.is_active or decoded.token_version != user.token_version:
        raise HTTPException(status_code=401, detail="Refresh token inválido ou expirado.")

    return _issue_token_pair(user)


@router.post("/change-password", response_model=Token)
def change_password(
    payload: ChangePassword, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Token:
    """Troca a senha do usuário autenticado. Isso invalida todos os tokens
    emitidos anteriormente (token_version incrementado) e devolve um novo
    par de tokens já válido, para que a sessão atual continue funcionando."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")

    user.hashed_password = hash_password(payload.new_password)
    user.token_version += 1
    db.commit()
    db.refresh(user)

    log_activity(user.id, "change_password", "Senha alterada com sucesso.")
    return _issue_token_pair(user)


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)) -> models.User:
    """Devolve os dados do usuário autenticado (usado pelo frontend para
    saber o nome de usuário e se é administrador, sem precisar decodificar
    o token no navegador)."""
    return user
