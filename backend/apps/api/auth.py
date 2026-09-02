"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from apps.core.permissions import get_current_user
from apps.core.config import settings
from apps.core.security import create_access_token
from apps.core.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter
from apps.db.session import get_db
from apps.models.persistence import UserRecord
from apps.schemas.auth import AccessToken, CurrentUser, LoginRequest
from apps.services.auth_service import AuthService

router = APIRouter()
login_limiter = SlidingWindowRateLimiter(
    attempts=settings.login_rate_limit_attempts,
    window_seconds=settings.login_rate_limit_window_seconds,
)


@router.post("/login", response_model=AccessToken)
async def login(
    credentials: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
) -> AccessToken:
    client_key = request.client.host if request.client else "unknown"
    try:
        login_limiter.check(client_key)
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts; try again later",
            headers={"Retry-After": str(settings.login_rate_limit_window_seconds)},
        ) from None
    user = AuthService(session).authenticate(credentials.email, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    login_limiter.reset(client_key)
    token, expires_at = create_access_token(str(user.id))
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=settings.app_env.lower() != "development",
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/api/v1",
    )
    return AccessToken(access_token=token, expires_at=expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    response.delete_cookie("access_token", path="/api/v1", samesite="lax")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=CurrentUser)
async def current_user(user: UserRecord = Depends(get_current_user)) -> CurrentUser:
    return CurrentUser(
        id=str(user.id), email=user.email, full_name=user.full_name,
        role=user.role, is_active=user.is_active,
    )
