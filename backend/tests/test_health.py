from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_api_health_endpoint() -> None:
    """Ensure /api/health responds with 200 and safe metadata."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "lolixco-pilot-api"
    assert "version" in data
    assert "timestamp" in data
    assert "environment" in data

    # Verify no secrets or private keys leaked in response payload
    forbidden_keys = [
        "MODEL_API_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_ACCESS_KEY_ID",
        "key",
        "secret",
        "token",
    ]
    for key in forbidden_keys:
        assert key not in data
        assert key.lower() not in data


def test_root_health_endpoint() -> None:
    """Ensure /health alias also functions for platform health checks."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
