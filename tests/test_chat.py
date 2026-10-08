"""Testes do fluxo de chat (usando o provedor de fallback do LLM)."""


def test_chat_requires_authentication(client):
    response = client.post("/api/chat", json={"message": "Olá, Zeus"})
    assert response.status_code == 401


def test_chat_returns_reply(client, auth_headers):
    response = client.post(
        "/api/chat", json={"message": "Olá, Zeus"}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"]
    assert body["conversation_id"]


def test_chat_datetime_plugin_routes_correctly(client, auth_headers):
    response = client.post(
        "/api/chat", json={"message": "que horas são?"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["source"] == "plugin"


def test_conversation_history_persists(client, auth_headers):
    first = client.post(
        "/api/chat", json={"message": "primeira mensagem"}, headers=auth_headers
    ).json()
    conversation_id = first["conversation_id"]

    client.post(
        "/api/chat",
        json={"conversation_id": conversation_id, "message": "segunda mensagem"},
        headers=auth_headers,
    )

    messages = client.get(
        f"/api/chat/conversations/{conversation_id}/messages", headers=auth_headers
    ).json()
    assert len(messages) == 4  # 2 mensagens do usuário + 2 respostas do Zeus


def test_reminder_plugin_creates_and_lists(client, auth_headers):
    create = client.post(
        "/api/chat", json={"message": "lembre-me de pagar a conta de luz"}, headers=auth_headers
    )
    assert create.status_code == 200
    assert create.json()["source"] == "plugin"

    listing = client.post(
        "/api/chat", json={"message": "quais são meus lembretes?"}, headers=auth_headers
    )
    assert listing.status_code == 200
    assert "pagar a conta de luz" in listing.json()["reply"]


def test_user_cannot_read_other_users_conversation(client, auth_headers, other_auth_headers):
    """Correção de segurança: uma conversa só pode ser lida pelo seu dono."""
    first = client.post(
        "/api/chat", json={"message": "mensagem privada da tony"}, headers=auth_headers
    ).json()
    conversation_id = first["conversation_id"]

    response = client.get(
        f"/api/chat/conversations/{conversation_id}/messages", headers=other_auth_headers
    )
    assert response.status_code == 404
