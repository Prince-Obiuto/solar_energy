"""Password hashing and JWT helpers with normalized authentication errors."""

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from apps.core.config import settings


password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
DUMMY_PASSWORD_HASH = password_context.hash("timing-only-password")


class InvalidTokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_context.verify(password, password_hash)
    except (TypeError, ValueError):
        return False


def create_access_token(subject: str, *, now: datetime | None = None) -> tuple[str, datetime]:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    token = jwt.encode(
        {"sub": subject, "iat": issued_at, "exp": expires_at, "type": "access"},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise InvalidTokenError("Invalid or expired access token") from exc
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject or payload.get("type") != "access":
        raise InvalidTokenError("Invalid or expired access token")
    return subject
