"""JWT authentication and reusable hierarchical role dependencies."""

import uuid
from collections.abc import Callable

from fastapi import Cookie, Depends, HTTPException, WebSocket, WebSocketException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from apps.core.security import InvalidTokenError, decode_access_token
from apps.db.session import get_db
from apps.models import UserRole
from apps.models.persistence import UserRecord


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
ROLE_LEVEL = {UserRole.STUDENT: 1, UserRole.STAFF: 2, UserRole.ADMIN: 3}


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials are invalid or expired",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    bearer_token: str | None = Depends(oauth2_scheme),
    access_token: str | None = Cookie(default=None),
    session: Session = Depends(get_db),
) -> UserRecord:
    token = bearer_token or access_token
    try:
        if token is None:
            raise InvalidTokenError
        user_id = uuid.UUID(decode_access_token(token))
    except (InvalidTokenError, ValueError):
        raise authentication_error() from None
    user = session.get(UserRecord, user_id)
    if user is None or not user.is_active:
        raise authentication_error()
    return user


def get_websocket_user(websocket: WebSocket, session: Session = Depends(get_db)) -> UserRecord:
    token = websocket.cookies.get("access_token")
    try:
        if token is None:
            raise InvalidTokenError
        user_id = uuid.UUID(decode_access_token(token))
    except (InvalidTokenError, ValueError):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from None
    user = session.get(UserRecord, user_id)
    if user is None or not user.is_active:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return user


def require_role(minimum: UserRole) -> Callable[..., UserRecord]:
    def dependency(user: UserRecord = Depends(get_current_user)) -> UserRecord:
        try:
            actual = UserRole(user.role)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions") from None
        if ROLE_LEVEL[actual] < ROLE_LEVEL[minimum]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return dependency


require_student = require_role(UserRole.STUDENT)
require_staff = require_role(UserRole.STAFF)
require_admin = require_role(UserRole.ADMIN)
