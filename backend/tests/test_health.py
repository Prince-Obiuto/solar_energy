"""Application health endpoint tests."""

from fastapi.testclient import TestClient


EXPECTED_HEALTH = {
    "status": "ok",
    "service": "solar-energy-backend",
    "version": "0.1.0",
}


def test_root_endpoint(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Smart Renewable Energy Management System",
        "version": "0.1.0",
        "docs": "/docs",
    }


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == EXPECTED_HEALTH


def test_versioned_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == EXPECTED_HEALTH


def test_swagger_docs_are_available(client: TestClient) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()


def test_development_cors_allows_react_frontend(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
