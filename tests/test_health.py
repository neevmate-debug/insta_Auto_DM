"""
Automated unit tests for the health check and discovery endpoints.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_health_endpoint():
    """
    Tests that the root /health endpoint returns HTTP 200 and expected status schema.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "instagram-automation-service"
    assert "environment" in data
    assert "version" in data
    assert "timestamp" in data


def test_api_v1_health_endpoint():
    """
    Tests that the versioned /api/v1/health endpoint returns HTTP 200.
    """
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "instagram-automation-service"


def test_root_index_endpoint():
    """
    Tests that the root GET / endpoint returns service information and docs links.
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["documentation"] == "/docs"
    assert data["health_check"] == "/health"
