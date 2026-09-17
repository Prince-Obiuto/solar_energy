"""Focused tests for final security hardening primitives."""

import asyncio

from fastapi import Response
from fastapi.exceptions import RequestValidationError

from apps.api.auth import logout
from apps.core.config import Settings
from apps.core.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter
from apps.main import sanitized_validation_error


def test_sliding_window_rate_limit_and_reset() -> None:
    now = [10.0]
    limiter = SlidingWindowRateLimiter(attempts=2, window_seconds=5, clock=lambda: now[0])
    limiter.check("client")
    limiter.check("client")
    try:
        limiter.check("client")
    except RateLimitExceeded:
        pass
    else:
        raise AssertionError("third attempt should be rejected")
    now[0] = 16.0
    limiter.check("client")
    limiter.reset("client")
    limiter.check("client")


def test_production_rejects_default_secret_and_wildcard_cors() -> None:
    for values in (
        {"app_env": "production", "jwt_secret_key": "development-only-change-me"},
        {"app_env": "production", "jwt_secret_key": "configured-secure-value", "cors_origins": "*"},
        {"app_env": "production", "jwt_secret_key": "configured-secure-value", "allowed_hosts": "*"},
    ):
        try:
            Settings(_env_file=None, **values)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe production configuration should fail")


def test_logout_clears_authentication_cookie() -> None:
    response = asyncio.run(logout(Response()))
    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert "access_token=" in cookie and "Max-Age=0" in cookie and "Path=/api/v1" in cookie


def test_validation_response_does_not_echo_submitted_secret() -> None:
    secret = "never-return-this-password"
    error = RequestValidationError([
        {"type": "string_too_short", "loc": ("body", "password"), "msg": "too short", "input": secret}
    ])
    response = asyncio.run(sanitized_validation_error(None, error))
    assert secret.encode() not in response.body
    assert b'"input"' not in response.body
