"""Testes das rotas REST de lembretes."""


def test_create_list_and_complete_reminder(client, auth_headers):
    created = client.post(
        "/api/reminders", json={"content": "Levar o carro para revisão"}, headers=auth_headers
    )
    assert created.status_code == 201
    reminder_id = created.json()["id"]

    pending = client.get("/api/reminders", headers=auth_headers).json()
    assert len(pending) == 1
    assert pending[0]["content"] == "Levar o carro para revisão"

    done = client.patch(f"/api/reminders/{reminder_id}/done", headers=auth_headers)
    assert done.status_code == 200
    assert done.json()["done"] is True

    pending_after = client.get("/api/reminders", headers=auth_headers).json()
    assert pending_after == []


def test_reminders_are_isolated_per_user(client, auth_headers, other_auth_headers):
    client.post("/api/reminders", json={"content": "Segredo da tony"}, headers=auth_headers)
    other_pending = client.get("/api/reminders", headers=other_auth_headers).json()
    assert other_pending == []
