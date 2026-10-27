"""Login / logout / whoami and the `require_user` dependency guarding the data API."""

import asyncio

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field, SecretStr

from app.core.config import Settings
from app.core.security import credentials_match, issue_token, verify_token


class NotAuthenticatedError(Exception):
    """No valid session / bad credentials. Mapped to a 401 error envelope."""


class LoginRequest(BaseModel):
    username: str = Field(max_length=128)
    password: SecretStr = Field(max_length=256)


class Me(BaseModel):
    username: str


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def session_user(request: Request) -> str | None:
    s = _settings(request)
    token = request.cookies.get(s.session_cookie)
    return verify_token(token, s.session_secret.get_secret_value()) if token else None


def is_authenticated(request: Request) -> bool:
    return not _settings(request).auth_enabled or session_user(request) is not None


def require_user(request: Request) -> str:
    """FastAPI dependency: the signed-in username, or 401."""
    if not _settings(request).auth_enabled:
        return "anonymous"
    user = session_user(request)
    if user is None:
        raise NotAuthenticatedError("Sign in required")
    return user


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=Me)
async def login(body: LoginRequest, request: Request, response: Response) -> Me:
    s = _settings(request)
    if not s.auth_enabled:
        return Me(username="anonymous")
    if not credentials_match(
        body.username,
        body.password.get_secret_value(),
        s.auth_username,
        s.auth_password.get_secret_value(),
    ):
        # Note: fixed delay, not real rate limiting (serverless has no shared state);
        # add an edge/WAF rule or a shared store (Redis) if brute-force becomes a concern.
        await asyncio.sleep(0.5)
        raise NotAuthenticatedError("Invalid username or password")
    ttl = s.session_ttl_hours * 3600
    response.set_cookie(
        s.session_cookie,
        issue_token(s.auth_username, s.session_secret.get_secret_value(), ttl),
        max_age=ttl,
        httponly=True,
        samesite="lax",
        # Behind Vercel's proxy the app sees http; trust the forwarded scheme.
        secure=request.headers.get("x-forwarded-proto", request.url.scheme) == "https",
        path="/",
    )
    return Me(username=s.auth_username)


@router.post("/logout", status_code=204)
async def logout(request: Request) -> Response:
    response = Response(status_code=204)
    response.delete_cookie(_settings(request).session_cookie, path="/")
    return response


@router.get("/me", response_model=Me)
async def me(request: Request) -> Me:
    return Me(username=require_user(request))
