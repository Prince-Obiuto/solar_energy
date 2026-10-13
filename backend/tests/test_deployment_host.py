"""Host allowlist and reverse-proxy contracts for LAN hostname/IP access."""

from pathlib import Path

from pydantic import SecretStr

from apps.core.config import Settings


REPOSITORY = Path(__file__).resolve().parents[2]


def test_production_host_allowlist_keeps_hostname_and_ip_explicit():
    settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret_key=SecretStr("test-only-nondefault-jwt-secret"),
        allowed_hosts="solar-energy.ift.internal,10.10.10.6,localhost,127.0.0.1",
    )
    assert settings.allowed_host_list == [
        "solar-energy.ift.internal", "10.10.10.6", "localhost", "127.0.0.1",
    ]
    assert "*" not in settings.allowed_host_list


def test_nginx_preserves_requested_host_for_https_spa_api_and_websocket():
    config = (REPOSITORY / "deployment/nginx/default.conf").read_text()
    assert "listen 80 default_server;" in config
    assert "return 308 https://$host$request_uri;" in config
    assert "listen 443 ssl default_server;" in config
    assert "server_name _;" in config
    assert "proxy_set_header Host $host;" in config
    assert "location /api/ {" in config
    assert "location = /api/v1/ws/energy {" in config
    assert "try_files $uri $uri/ /index.html;" in config
