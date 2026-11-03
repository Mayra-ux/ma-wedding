from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_200() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"


def test_no_public_api_docs() -> None:
    client = TestClient(create_app())
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
