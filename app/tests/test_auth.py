# tests/test_auth.py
def test_login_returns_token(client):
    resp = client.post("/auth/login")
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert "access_token" in data["token"]


def test_refresh_with_valid_token(client, auth_headers):
    resp = client.post("/auth/refresh", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
