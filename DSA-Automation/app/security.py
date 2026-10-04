"""Protects the review dashboard and admin endpoints.

The app can commit to your GitHub repo, so once it is deployed the review
pages must NOT be public. We use HTTP Basic auth with credentials from
environment variables, plus brute-force protection:
  - a short delay after every failed attempt
  - a temporary lockout after repeated failures from the same address
If REVIEW_PASSWORD is not set, access is denied (secure by default).
"""
import asyncio
import os
import secrets
import time

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_basic = HTTPBasic()

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60
FAILURE_DELAY_SECONDS = 1.0

# client key -> list of failure timestamps (in memory, per process)
_failures: dict[str, list[float]] = {}


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _recent_failures(key: str) -> list[float]:
    cutoff = time.time() - WINDOW_SECONDS
    recent = [t for t in _failures.get(key, []) if t > cutoff]
    if recent:
        _failures[key] = recent
    else:
        _failures.pop(key, None)
    return recent


def reset_failures() -> None:
    """Used by tests."""
    _failures.clear()


async def require_auth(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(_basic),
) -> str:
    expected_user = os.getenv("REVIEW_USERNAME", "admin")
    expected_password = os.getenv("REVIEW_PASSWORD")

    if not expected_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="REVIEW_PASSWORD is not configured on the server.",
        )

    key = _client_key(request)

    if len(_recent_failures(key)) >= MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again in 15 minutes.",
        )

    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), expected_user.encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"), expected_password.encode("utf-8")
    )

    if not (user_ok and password_ok):
        _failures.setdefault(key, []).append(time.time())
        await asyncio.sleep(FAILURE_DELAY_SECONDS)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    _failures.pop(key, None)
    return credentials.username