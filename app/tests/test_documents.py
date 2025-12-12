# tests/test_documents.py
from unittest.mock import patch


def test_analyze_document_requires_auth(client):
    resp = client.post(
        "/documents/analyze",
        files={"file": ("fake.pdf", b"hola", "application/pdf")},
    )
    assert resp.status_code in (401, 403)


@patch("app.routers.documents.extract_text_from_document")
def test_analyze_document_factura(mock_extract, client, auth_headers):
    # Simulamos que el OCR devolvió el texto de la factura
    mock_extract.return_value = """
    Factura
    Fecha de factura: 17/04/2024
    Numero de factura: 2024-0001
    Orlando Juan Loban Empresa de logistica, S. L.
    Producto 1 2 100 200,00
    Producto 3 7 93 651,00
    Total: 1.308,8
    """

    resp = client.post(
        "/documents/analyze",
        headers=auth_headers,
        files={"file": ("factura.jpg", b"fake-bytes", "image/jpeg")},
        data={"description": "Factura de prueba"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["doc_type"] == "factura"
    ext = data["extracted"]
    assert ext["cliente"] == "Orlando Juan Loban"
    assert ext["proveedor"].startswith("Empresa de logistica")
    assert ext["numero_factura"] == "2024-0001"
    assert ext["total"].startswith("1.308")
    assert len(ext["items"]) >= 1


@patch("app.routers.documents.extract_text_from_document")
def test_analyze_document_informacion(mock_extract, client, auth_headers):
    mock_extract.return_value = "Este es un texto cualquiera, sin palabras de factura."

    resp = client.post(
        "/documents/analyze",
        headers=auth_headers,
        files={"file": ("nota.txt", b"fake", "image/jpeg")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["doc_type"] == "informacion"
    assert data["extracted"]["kind"] == "informacion"
