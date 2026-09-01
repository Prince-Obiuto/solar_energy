"""Create the first administrator from environment-only credentials."""

from apps.core.config import settings
from apps.db.session import session_scope
from apps.services.auth_service import AuthService


def main() -> None:
    if settings.initial_admin_email is None or settings.initial_admin_password is None:
        raise SystemExit("INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD are required")
    with session_scope() as session:
        user = AuthService(session).bootstrap_admin(
            settings.initial_admin_email,
            settings.initial_admin_password.get_secret_value(),
            settings.initial_admin_full_name,
        )
    print(f"Initial administrator is ready: {user.email}")


if __name__ == "__main__":
    main()
