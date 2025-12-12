# tests/test_files.py
import io


def test_upload_csv_requires_auth(client):
    # Sin token debería fallar
    resp = client.post(
        "/files/upload-csv",
        files={"file": ("test.csv", b"id,valor\n1,100\n")},
    )
    assert resp.status_code in (401, 403)


def test_upload_csv_ok(client, auth_headers):
    csv_bytes = b"id,valor\n1,100\n2,200\n"
    resp = client.post(
        "/files/upload-csv",
        headers=auth_headers,
        files={"file": ("test.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "file_id" in data or "rows_inserted" in data
