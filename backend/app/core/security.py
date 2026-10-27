"""Stateless signed session tokens and credential checks (stdlib only).

Token = base64url(payload).base64url(HMAC-SHA256(payload)), payload = "<username>|<expiry epoch>".
Stateless on purpose: serverless instances share no memory, so there is no session store.
"""

import base64
import hashlib
import hmac
import time


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(payload: bytes, secret: str) -> bytes:
    return hmac.new(secret.encode(), payload, hashlib.sha256).digest()


def issue_token(username: str, secret: str, ttl_s: int, now: float | None = None) -> str:
    expiry = int((time.time() if now is None else now) + ttl_s)
    payload = f"{username}|{expiry}".encode()
    return f"{_b64(payload)}.{_b64(_mac(payload, secret))}"


def verify_token(token: str, secret: str, now: float | None = None) -> str | None:
    """Username if the token is authentic and unexpired, else None. Never raises."""
    try:
        body, sig = token.split(".", 1)
        payload = _unb64(body)
        if not hmac.compare_digest(_unb64(sig), _mac(payload, secret)):
            return None
        username, expiry = payload.decode().rsplit("|", 1)
        if int(expiry) < (time.time() if now is None else now):
            return None
        return username
    except ValueError:  # bad base64, bad utf-8, bad int, missing separators
        return None


def credentials_match(
    username: str, password: str, expected_username: str, expected_password: str
) -> bool:
    """Constant-time comparison of both fields (no early exit on the username)."""
    user_ok = hmac.compare_digest(username.encode(), expected_username.encode())
    pass_ok = hmac.compare_digest(password.encode(), expected_password.encode())
    return user_ok and pass_ok
