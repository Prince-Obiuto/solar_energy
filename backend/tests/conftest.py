"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from apps.main import app


@pytest.fixture
def client() -> TestClient:
    """Provide an application test client."""

    return TestClient(app)
