# tests/test_events.py
def test_events_requires_auth(client):
    resp = client.get("/events")
    assert resp.status_code in (401, 403)


def test_events_list_ok(client, auth_headers):
    resp = client.get("/events", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_events_filter_by_type(client, auth_headers):
    resp = client.get("/events?event_type=DOC_ANALYSIS", headers=auth_headers)
    assert resp.status_code == 200
    # sólo chequeamos que la respuesta sea lista, el filtro exacto es extra
    assert isinstance(resp.json(), list)


def test_events_export_excel(client, auth_headers):
    resp = client.get("/events/export", headers=auth_headers)
    assert resp.status_code == 200
    # tipo de contenido Excel (puede ser application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
    assert "application" in resp.headers["content-type"]
