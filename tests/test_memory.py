"""Testes de anotações e preferências (memória estruturada)."""


def test_create_and_list_note(client, auth_headers):
    response = client.post(
        "/api/memory/notes",
        json={"title": "Lembrete", "content": "Comprar novo reator arc.", "tags": "pessoal"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Lembrete"

    notes = client.get("/api/memory/notes", headers=auth_headers).json()
    assert len(notes) == 1
    assert notes[0]["content"] == "Comprar novo reator arc."


def test_set_and_get_preference(client, auth_headers):
    client.post(
        "/api/memory/preferences", json={"key": "idioma", "value": "pt-BR"}, headers=auth_headers
    )
    prefs = client.get("/api/memory/preferences", headers=auth_headers).json()
    assert prefs["idioma"] == "pt-BR"
