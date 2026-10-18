from tests.conftest import register


def test_register_and_me(client):
    headers = register(client)
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "a@example.com"


def test_duplicate_email_rejected(client):
    register(client)
    r = client.post(
        "/api/auth/register", json={"email": "A@example.com", "password": "password123"}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


def test_weak_password_and_bad_email_rejected(client):
    assert (
        client.post(
            "/api/auth/register", json={"email": "x@y.com", "password": "short"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/auth/register", json={"email": "not-an-email", "password": "password123"}
        ).status_code
        == 422
    )


def test_login_success_and_failure(client):
    register(client)
    ok = client.post("/api/auth/login", json={"email": "a@example.com", "password": "password123"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrongpass1"})
    assert bad.status_code == 401


def test_protected_routes_require_token(client):
    assert client.get("/api/conversations").status_code == 401
    assert (
        client.get("/api/conversations", headers={"Authorization": "Bearer junk"}).status_code
        == 401
    )


def test_error_body_has_request_id(client):
    r = client.get("/api/conversations")
    assert r.json()["error"]["request_id"]
    assert r.headers["x-request-id"]
