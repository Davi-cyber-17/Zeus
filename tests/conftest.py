"""Fixtures compartilhadas pelos testes automatizados do Zeus."""
import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LLM_API_KEY"] = ""  # força o provedor de fallback (sem chamadas externas)
os.environ["SECRET_KEY"] = "test-secret-key"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.database import Base, get_db
from backend.main import app


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    client.post(
        "/api/auth/register",
        json={"username": "tony", "email": "tony@zeus.ai", "password": "starkindustries"},
    )
    response = client.post(
        "/api/auth/login", data={"username": "tony", "password": "starkindustries"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def other_auth_headers(client):
    """Segundo usuário, usado para testar isolamento entre contas (IDOR)."""
    client.post(
        "/api/auth/register",
        json={"username": "pepper", "email": "pepper@zeus.ai", "password": "starkindustries"},
    )
    response = client.post(
        "/api/auth/login", data={"username": "pepper", "password": "starkindustries"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
