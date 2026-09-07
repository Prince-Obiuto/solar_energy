"""Shared pytest fixtures with deterministic application configuration."""

import os

# Settings are instantiated while importing apps.main. Environment overrides
# must therefore be installed before any application import in this process.
os.environ["APP_ENV"] = "test"
os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1,testserver"
os.environ["TUYA_DEVICE_FILE"] = "/tmp/solar-energy-pytest-no-hardware.json"

import pytest
from fastapi.testclient import TestClient

from apps.main import app
from apps.jobs.energy_collector import CollectorSnapshot, configure_energy_collector, get_energy_collector


class NoHardwareCollector:
    """Deterministic lifespan-safe collector used unless a test supplies one."""

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def get_snapshot(self) -> CollectorSnapshot:
        return CollectorSnapshot()


@pytest.fixture(autouse=True)
def isolate_application_collector():
    original = get_energy_collector()
    configure_energy_collector(NoHardwareCollector())
    try:
        yield
    finally:
        configure_energy_collector(original)


@pytest.fixture
def client() -> TestClient:
    """Provide an application test client."""

    return TestClient(app, base_url="https://testserver")
