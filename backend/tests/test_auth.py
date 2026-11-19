from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app import cli
from app.config import settings
from conftest import PASSWORD, upload, make_csv, row


def register(client, email="new@example.org", password=PASSWORD):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def test_register_login_me_roundtrip(client):
    r = register(client)
    assert r.status_code == 201 and r.json()["role"] == "researcher" and "password" not in r.text
    tok = client.post("/api/auth/login", json={"email": "NEW@example.org", "password": PASSWORD}).json()
    assert tok["token_type"] == "bearer" and tok["user"]["email"] == "new@example.org"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "new@example.org"


def test_cannot_self_register_as_admin(client):
    r = client.post("/api/auth/register", json={"email": "evil@example.org", "password": PASSWORD, "role": "admin"})
    assert r.status_code == 201 and r.json()["role"] == "researcher"


def test_duplicate_email_case_insensitive(client):
    assert register(client, "dup@example.org").status_code == 201
    assert register(client, "DUP@example.org").status_code == 409


@pytest.mark.parametrize("email,password", [("not-an-email", PASSWORD), ("a@example.org", "short"), ("a@example.org", "é" * 40)])
def test_register_validation(client, email, password):
    assert register(client, email, password).status_code == 422


def test_registration_can_be_disabled(client):
    settings.allow_registration = False
    assert register(client).status_code == 403


def test_login_failures_are_uniform(client):
    register(client)
    wrong = client.post("/api/auth/login", json={"email": "new@example.org", "password": "wrong-password-1"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.org", "password": "wrong-password-1"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()


def test_login_throttled_after_repeated_failures(client):
    register(client)
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "new@example.org", "password": "bad-password-1"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "new@example.org", "password": PASSWORD})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_oauth2_form_login_for_swagger(client):
    register(client)
    r = client.post("/api/auth/token", data={"username": "new@example.org", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["access_token"]


def test_me_requires_valid_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def _token(sub, **over):
    now = datetime.now(timezone.utc)
    claims = {"sub": str(sub), "iss": "cyclonelens-api", "iat": now, "exp": now + timedelta(minutes=5), **over}
    return jwt.encode(claims, settings.secret_key, algorithm="HS256")


def test_expired_and_foreign_tokens_rejected(client, user_headers):
    uid = client.get("/api/auth/me", headers=user_headers).json()["id"]
    expired = _token(uid, exp=datetime.now(timezone.utc) - timedelta(minutes=1))
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    wrong_iss = _token(uid, iss="someone-else")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {wrong_iss}"}).status_code == 401
    forged = jwt.encode({"sub": str(uid), "iss": "cyclonelens-api", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                        "another-secret-" + "z" * 32, algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {_token(uid)}"}).status_code == 200


def test_protected_endpoints_require_auth(client):
    assert client.post("/api/ml/predict-track", json={"latitude": 1, "longitude": 1}).status_code == 401
    assert client.get("/api/predictions").status_code == 401
    assert client.post("/api/ml/analyze-image", files={"file": ("a.png", b"x", "image/png")}).status_code == 401
    assert upload(client, {}, make_csv([row()])).status_code == 401


def test_import_requires_admin_role(client, user_headers):
    r = upload(client, user_headers, make_csv([row()]))
    assert r.status_code == 403


def test_public_read_endpoints_need_no_login(client):
    for path in ("/api/health", "/api/cyclones", "/api/storms", "/api/analytics/overview", "/api/ml/models", "/api/data/imports"):
        assert client.get(path).status_code == 200, path


def test_create_admin_cli_creates_and_promotes(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)
    assert cli.main(["create-admin", "--email", "Boss@example.org"]) == 0
    tok = client.post("/api/auth/login", json={"email": "boss@example.org", "password": PASSWORD}).json()
    assert tok["user"]["role"] == "admin"
    register(client, "promote@example.org")
    assert cli.main(["create-admin", "--email", "promote@example.org"]) == 0
    assert client.post("/api/auth/login", json={"email": "promote@example.org", "password": PASSWORD}).json()["user"]["role"] == "admin"


def test_create_admin_cli_rejects_weak_password(monkeypatch, capsys):
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    assert cli.main(["create-admin", "--email", "a@example.org"]) == 1
