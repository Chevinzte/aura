from fastapi.testclient import TestClient

from aura_backend.main import create_app


def test_health_check_reports_running_service() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
