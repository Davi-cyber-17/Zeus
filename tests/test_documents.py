"""Testes de upload, listagem e exclusão de documentos."""
import io


def test_upload_list_and_delete_document(client, auth_headers):
    upload = client.post(
        "/api/documents/upload",
        files={"file": ("nota.txt", io.BytesIO(b"conteudo de teste do zeus"), "text/plain")},
        headers=auth_headers,
    )
    assert upload.status_code == 200
    document_id = upload.json()["id"]
    assert upload.json()["indexed"] is True

    docs = client.get("/api/documents", headers=auth_headers).json()
    assert any(d["id"] == document_id for d in docs)

    deleted = client.delete(f"/api/documents/{document_id}", headers=auth_headers)
    assert deleted.status_code == 204

    docs_after = client.get("/api/documents", headers=auth_headers).json()
    assert not any(d["id"] == document_id for d in docs_after)


def test_upload_rejects_unsupported_extension(client, auth_headers):
    upload = client.post(
        "/api/documents/upload",
        files={"file": ("virus.exe", io.BytesIO(b"conteudo"), "application/octet-stream")},
        headers=auth_headers,
    )
    assert upload.status_code == 400


def test_upload_sanitizes_path_traversal_filename(client, auth_headers):
    """Correção de segurança: nomes de arquivo com '../' não devem escapar
    da pasta de documentos configurada."""
    upload = client.post(
        "/api/documents/upload",
        files={"file": ("../../etc/malicioso.txt", io.BytesIO(b"conteudo"), "text/plain")},
        headers=auth_headers,
    )
    assert upload.status_code == 200
    # O nome salvo não deve conter mais nenhum separador de diretório.
    assert "/" not in upload.json()["filename"]
    assert upload.json()["filename"] == "malicioso.txt"
