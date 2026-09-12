"""Load mounted container secrets, then exec the requested existing command.

No setup, migration, key creation, or hardware work occurs here. Do not import
application settings before constructing the environment.
"""

import os
from pathlib import Path
import sys

from sqlalchemy.engine import URL


class ContainerConfigurationError(RuntimeError):
    """Safe operator error that contains neither secret values nor file paths."""


def read_secret(environment: dict[str, str], variable: str) -> str:
    try:
        value = Path(environment[variable]).read_text(encoding="utf-8").rstrip("\r\n")
    except (KeyError, OSError, UnicodeError):
        raise ContainerConfigurationError(f"Required secret file for {variable} cannot be read") from None
    if not value or "\n" in value or "\r" in value or "\x00" in value:
        raise ContainerConfigurationError(f"Required secret file for {variable} is invalid")
    return value


def prepare_environment(environment: dict[str, str]) -> dict[str, str]:
    result = environment.copy()
    password = read_secret(result, "POSTGRES_PASSWORD_FILE")
    jwt = read_secret(result, "JWT_SECRET_KEY_FILE")
    if len(jwt) < 32:
        raise ContainerConfigurationError("JWT signing key must contain at least 32 characters")
    try:
        port = int(result["POSTGRES_PORT"])
        if not 1 <= port <= 65535 or not result["POSTGRES_USER"] or not result["POSTGRES_DB"]:
            raise ValueError
        result["DATABASE_URL"] = URL.create(
            "postgresql+psycopg",
            username=result["POSTGRES_USER"],
            password=password,
            host="127.0.0.1",
            port=port,
            database=result["POSTGRES_DB"],
        ).render_as_string(hide_password=False)
    except (KeyError, ValueError, TypeError):
        raise ContainerConfigurationError("Database connection configuration is invalid") from None
    result["JWT_SECRET_KEY"] = jwt
    return result


def main() -> int:
    if len(sys.argv) < 2:
        print("A container command is required", file=sys.stderr)
        return 1
    try:
        environment = prepare_environment(dict(os.environ))
        os.execvpe(sys.argv[1], sys.argv[1:], environment)
    except ContainerConfigurationError as exc:
        print(str(exc), file=sys.stderr)
    except OSError:
        print("The container command could not be started", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
