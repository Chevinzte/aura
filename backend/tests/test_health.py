import re

from fastapi.testclient import TestClient

from aura_backend.main import create_app

INTERNAL_API_KEY = "test-internal-api-key-1234567890"


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


def test_health_check_does_not_require_internal_authentication() -> None:
    response = TestClient(
        create_app(internal_api_key=INTERNAL_API_KEY)
    ).get(
        "/health",
        headers={"Authorization": "Bearer wrong-key"},
    )

    assert response.status_code == 200


def test_business_routes_require_internal_authentication() -> None:
    client = TestClient(create_app(internal_api_key=INTERNAL_API_KEY))

    missing = client.get("/v1/wardrobe/correction-options")
    incorrect = client.get(
        "/v1/wardrobe/correction-options",
        headers={"Authorization": "Bearer wrong-key"},
    )

    for response in (missing, incorrect):
        assert response.status_code == 401
        assert response.json() == {"detail": "BACKEND_AUTHENTICATION_FAILED"}
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert re.fullmatch(r"[A-F0-9]{12}", response.headers["X-Request-ID"])


def test_business_routes_accept_internal_authentication() -> None:
    response = TestClient(create_app(internal_api_key=INTERNAL_API_KEY)).get(
        "/v1/wardrobe/correction-options",
        headers={"Authorization": f"Bearer {INTERNAL_API_KEY}"},
    )

    assert response.status_code == 200
