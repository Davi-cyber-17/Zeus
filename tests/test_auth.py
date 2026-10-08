"""Testes de registro e login."""


def test_register_creates_first_user_as_admin(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "tony", "email": "tony@zeus.ai", "password": "starkindustries"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "tony"
    assert body["is_admin"] is True


def test_register_duplicate_username_fails(client):
    payload = {"username": "tony", "email": "tony@zeus.ai", "password": "starkindustries"}
    client.post("/api/auth/register", json=payload)
    response = client.post(
        "/api/auth/register",
        json={"username": "tony", "email": "other@zeus.ai", "password": "starkindustries"},
    )
    assert response.status_code == 400


def test_login_success_returns_token(client):
    client.post(
        "/api/auth/register",
        json={"username": "tony", "email": "tony@zeus.ai", "password": "starkindustries"},
    )
    response = client.post("/api/auth/login", data={"username": "tony", "password": "starkindustries"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password_fails(client):
    client.post(
        "/api/auth/register",
        json={"username": "tony", "email": "tony@zeus.ai", "password": "starkindustries"},
    )
    response = client.post("/api/auth/login", data={"username": "tony", "password": "wrong"})
    assert response.status_code == 401


def test_login_returns_refresh_token(client):
    client.post(
        "/api/auth/register",
        json={"username": "tony", "email": "tony@zeus.ai", "password": "starkindustries"},
    )
    response = client.post("/api/auth/login", data={"username": "tony", "password": "starkindustries"})
    assert "refresh_token" in response.json()


def test_refresh_token_issues_new_access_token(client):
    client.post(
        "/api/auth/register",
        json={"username": "tony", "email": "tony@zeus.ai", "password": "starkindustries"},
    )
    login = client.post("/api/auth/login", data={"username": "tony", "password": "starkindustries"}).json()

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()


def test_change_password_invalidates_old_access_token(client):
    client.post(
        "/api/auth/register",
        json={"username": "tony", "email": "tony@zeus.ai", "password": "starkindustries"},
    )
    login = client.post("/api/auth/login", data={"username": "tony", "password": "starkindustries"}).json()
    old_headers = {"Authorization": f"Bearer {login['access_token']}"}

    changed = client.post(
        "/api/auth/change-password",
        json={"current_password": "starkindustries", "new_password": "novoreatorarc123"},
        headers=old_headers,
    )
    assert changed.status_code == 200

    # O token antigo (emitido antes da troca de senha) não deve mais funcionar.
    stale_response = client.get("/api/chat/conversations", headers=old_headers)
    assert stale_response.status_code == 401

    # Mas o novo par de tokens devolvido na troca de senha funciona normalmente.
    new_headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    fresh_response = client.get("/api/chat/conversations", headers=new_headers)
    assert fresh_response.status_code == 200
