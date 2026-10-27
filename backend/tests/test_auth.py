import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import credentials_match, issue_token, verify_token
from app.main import create_app

SECRET = "x" * 40
CREDS = {"username": "desk", "password": "correct horse"}


def settings(**kw) -> Settings:
    base = {
        "auth_enabled": True,
        "auth_username": "desk",
        "auth_password": "correct horse",
        "session_secret": SECRET,
    }
    return Settings(**{**base, **kw})


@pytest.fixture
def client():
    return TestClient(create_app(settings()))


@pytest.fixture
def signed_in(client):
    assert client.post("/api/v1/auth/login", json=CREDS).status_code == 200
    return client


# ---- token primitives ----
def test_token_round_trip():
    assert verify_token(issue_token("desk", SECRET, 60, now=1000), SECRET, now=1030) == "desk"


def test_expired_token_rejected():
    assert verify_token(issue_token("desk", SECRET, 60, now=1000), SECRET, now=1061) is None


def test_token_with_other_secret_rejected():
    assert verify_token(issue_token("desk", SECRET, 60), "y" * 40) is None


def test_tampered_token_rejected():
    body, sig = issue_token("desk", SECRET, 60).split(".")
    forged = issue_token("admin", SECRET, 60).split(".")[0]
    assert verify_token(f"{forged}.{sig}", SECRET) is None


@pytest.mark.parametrize("junk", ["", "abc", "a.b", "....", "é.é", "e30.e30"])
def test_garbage_never_raises(junk):
    assert verify_token(junk, SECRET) is None


def test_username_containing_separator():
    assert verify_token(issue_token("a|b", SECRET, 60), SECRET) == "a|b"


def test_credentials_match_requires_both():
    assert credentials_match("u", "p", "u", "p")
    assert not credentials_match("u", "x", "u", "p")
    assert not credentials_match("x", "p", "u", "p")
    assert not credentials_match("ü", "p", "u", "p")  # non-ascii must not raise


# ---- configuration fails closed ----
@pytest.mark.parametrize(
    "kw",
    [{"auth_username": ""}, {"auth_password": ""}, {"session_secret": "short"}],
)
def test_app_refuses_weak_or_missing_auth_config(kw):
    with pytest.raises(ValidationError):
        settings(**kw)


def test_auth_can_be_disabled_explicitly():
    assert Settings(auth_enabled=False).auth_enabled is False


# ---- HTTP behaviour ----
DATA_ROUTES = [
    "/api/v1/ready",
    "/api/v1/delivery-days",
    "/api/v1/forecast?delivery_date=2026-01-15",
    "/api/v1/forecast/vintages?target=2026-01-15T12:00:00Z",
    "/api/v1/accuracy/summary",
    "/api/v1/accuracy/daily",
    "/api/v1/accuracy/by-horizon",
    "/api/v1/accuracy/by-hour",
    "/api/v1/accuracy/by-wind-level",
    "/api/v1/accuracy/errors",
]


@pytest.mark.parametrize("path", DATA_ROUTES)
def test_every_data_route_requires_a_session(client, path):
    r = client.get(path)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"
    assert "mw" not in r.text  # no data in the body


def test_health_is_public(client):
    assert client.get("/api/v1/health").status_code == 200


def test_bad_credentials_rejected_without_hint(client):
    for body in ({**CREDS, "password": "nope"}, {**CREDS, "username": "nobody"}):
        r = client.post("/api/v1/auth/login", json=body)
        assert r.status_code == 401
        assert r.json()["error"]["message"] == "Invalid username or password"
    assert "set-cookie" not in r.headers


def test_login_sets_hardened_cookie_and_unlocks_data():
    c = TestClient(create_app(settings()), base_url="https://testserver")
    r = c.post("/api/v1/auth/login", json=CREDS)
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "secure" in cookie
    assert c.get("/api/v1/delivery-days").status_code == 200
    assert c.get("/api/v1/auth/me").json() == {"username": "desk"}


def test_cookie_is_secure_behind_a_tls_terminating_proxy(client):
    r = client.post("/api/v1/auth/login", json=CREDS, headers={"x-forwarded-proto": "https"})
    assert "secure" in r.headers["set-cookie"].lower()


def test_cookie_not_secure_on_plain_http_dev(client):
    r = client.post("/api/v1/auth/login", json=CREDS)
    assert "secure" not in r.headers["set-cookie"].lower()


def test_logout_revokes_browser_session(signed_in):
    assert signed_in.post("/api/v1/auth/logout").status_code == 204
    assert signed_in.get("/api/v1/delivery-days").status_code == 401


def test_forged_cookie_rejected(client):
    client.cookies.set("ww_session", issue_token("desk", "z" * 40, 60))
    assert client.get("/api/v1/delivery-days").status_code == 401


def test_expired_session_rejected():
    c = TestClient(create_app(settings()))
    c.cookies.set("ww_session", issue_token("desk", SECRET, 60, now=1))
    assert c.get("/api/v1/delivery-days").status_code == 401


def test_responses_are_private_and_304_needs_a_session(signed_in):
    r = signed_in.get("/api/v1/delivery-days")
    assert "private" in r.headers["cache-control"]
    etag = r.headers["etag"]
    assert (
        signed_in.get("/api/v1/delivery-days", headers={"If-None-Match": etag}).status_code == 304
    )
    signed_in.cookies.clear()
    anon = signed_in.get("/api/v1/delivery-days", headers={"If-None-Match": etag})
    assert anon.status_code == 401
