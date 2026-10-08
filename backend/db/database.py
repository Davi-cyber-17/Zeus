"""
Zeus AI - Conexão com banco de dados
======================================
Usa SQLAlchemy, o que permite trocar SQLite (desenvolvimento) por
PostgreSQL (produção) apenas alterando a DATABASE_URL, sem tocar em
nenhuma outra parte do código — princípio de modularidade do projeto.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.core.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Cria todas as tabelas caso não existam. Chamado no startup da API."""
    from backend.db import models  # noqa: F401 (garante que os modelos sejam registrados)

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency do FastAPI: fornece uma sessão de banco por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager para uso fora de rotas (ex.: plugins, jobs, testes)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
