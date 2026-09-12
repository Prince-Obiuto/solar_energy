"""Container secret loading must preserve credentials without disclosing them."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url


ENTRYPOINT = Path(__file__).resolve().parents[1] / "docker" / "entrypoint.py"
spec = importlib.util.spec_from_file_location("container_entrypoint", ENTRYPOINT)
entrypoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entrypoint)


@pytest.fixture
def container_environment(tmp_path):
    password = tmp_path / "postgres_password"
    password.write_text("example-only:@/%?&+ password\n", encoding="utf-8")
    jwt = tmp_path / "jwt_secret"
    jwt.write_text("test-only-signing-key-that-is-long-enough\n", encoding="utf-8")
    return {
        "POSTGRES_PASSWORD_FILE": str(password),
        "JWT_SECRET_KEY_FILE": str(jwt),
        "POSTGRES_DB": "test_database",
        "POSTGRES_USER": "test:user",
        "POSTGRES_PORT": "15432",
        "DATABASE_URL": "must-not-use-stale-url",
        "JWT_SECRET_KEY": "must-not-use-stale-signing-key",
    }


def test_container_database_password_round_trips_special_characters(container_environment):
    prepared = entrypoint.prepare_environment(container_environment)
    url = make_url(prepared["DATABASE_URL"])
    assert url.password == "example-only:@/%?&+ password"
    assert url.username == "test:user"
    assert url.host == "127.0.0.1"
    assert url.port == 15432
    assert url.database == "test_database"
    assert prepared["JWT_SECRET_KEY"] == "test-only-signing-key-that-is-long-enough"
    assert container_environment["DATABASE_URL"] == "must-not-use-stale-url"


@pytest.mark.parametrize("name", ["POSTGRES_PASSWORD_FILE", "JWT_SECRET_KEY_FILE"])
def test_missing_container_secret_fails_without_path_or_value(container_environment, name):
    path = Path(container_environment[name])
    path.unlink()
    with pytest.raises(entrypoint.ContainerConfigurationError) as failure:
        entrypoint.prepare_environment(container_environment)
    assert str(path) not in str(failure.value)
    assert "example-only" not in str(failure.value)
    assert "test-only" not in str(failure.value)


@pytest.mark.parametrize("value", ["", "two\nlines", "nul\x00byte", "\xff"])
def test_invalid_container_secret_has_safe_error(container_environment, value):
    Path(container_environment["POSTGRES_PASSWORD_FILE"]).write_bytes(value.encode("latin-1"))
    with pytest.raises(entrypoint.ContainerConfigurationError, match="secret file"):
        entrypoint.prepare_environment(container_environment)


def test_short_jwt_secret_refused(container_environment):
    Path(container_environment["JWT_SECRET_KEY_FILE"]).write_text("too-short")
    with pytest.raises(entrypoint.ContainerConfigurationError, match="at least 32"):
        entrypoint.prepare_environment(container_environment)


@pytest.mark.parametrize("port", ["not-a-port", "0", "65536"])
def test_invalid_database_port_has_safe_error(container_environment, port):
    container_environment["POSTGRES_PORT"] = port
    with pytest.raises(entrypoint.ContainerConfigurationError, match="Database connection"):
        entrypoint.prepare_environment(container_environment)


def test_failed_entrypoint_never_prints_secret_details(container_environment, monkeypatch, capsys):
    monkeypatch.setattr(entrypoint.sys, "argv", ["entrypoint.py", "alembic", "current"])
    for key, value in container_environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(entrypoint.os, "execvpe", lambda *_args: (_ for _ in ()).throw(OSError("private details")))
    assert entrypoint.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "The container command could not be started\n"
