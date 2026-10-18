import re

from fastapi.testclient import TestClient

from aura_backend.main import create_app


def test_health_check_reports_running_service() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_echoes_valid_request_reference() -> None:
    response = TestClient(create_app()).get(
        "/health",
        headers={"X-Request-ID": "TESTREF12345"},
    )

    assert response.headers["X-Request-ID"] == "TESTREF12345"


def test_health_check_replaces_invalid_request_reference() -> None:
    response = TestClient(create_app()).get(
        "/health",
        headers={"X-Request-ID": "invalid reference"},
    )

    assert re.fullmatch(r"[A-F0-9]{12}", response.headers["X-Request-ID"])
