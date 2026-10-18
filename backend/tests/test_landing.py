from fastapi.testclient import TestClient

from aura_backend.main import create_app


def test_landing_page_presents_public_product_overview() -> None:
    response = TestClient(create_app()).get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "AURA" in response.text
    assert "Understand your" in response.text
    assert ">aesthetic</span>" in response.text
    assert "How AURA uses AI responsibly" in response.text
    assert 'href="/health"' in response.text
    assert 'id="visual-fit"' in response.text
    assert 'id="intentional-contrast"' in response.text
    assert 'name="match-perspective" checked' in response.text
    assert '<a class="hero-action" href="/try-aura"' in response.text
    assert (
        "The soft fabric and relaxed shape are similar to items"
        in response.text
    )
    assert (
        "The bright cobalt blue is stronger than the quieter colours"
        in response.text
    )


def test_landing_page_does_not_expose_private_access_or_secrets() -> None:
    response = TestClient(create_app()).get("/")

    assert "https://t.me/" not in response.text
    assert "TELEGRAM_BOT_TOKEN" not in response.text
    assert "AURA_INTERNAL_API_KEY" not in response.text
    assert "SUPABASE_SECRET_KEY" not in response.text


def test_landing_page_applies_restrictive_browser_headers() -> None:
    response = TestClient(create_app()).get("/")

    assert response.headers["content-security-policy"].startswith(
        "default-src 'none'"
    )
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_landing_page_serves_reference_wardrobe_assets() -> None:
    response = TestClient(create_app()).get("/static/landing/hero-wardrobe.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 1_000


def test_try_aura_redirects_to_configured_telegram_demo(monkeypatch) -> None:
    monkeypatch.setenv("AURA_PUBLIC_TELEGRAM_URL", "https://t.me/example_bot")

    response = TestClient(create_app()).get("/try-aura", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "https://t.me/example_bot"


def test_try_aura_rejects_missing_or_invalid_destination(monkeypatch) -> None:
    monkeypatch.setenv("AURA_PUBLIC_TELEGRAM_URL", "https://example.com/not-telegram")

    response = TestClient(create_app()).get("/try-aura")

    assert response.status_code == 503
    assert response.json() == {"detail": "PUBLIC_DEMO_LINK_NOT_CONFIGURED"}
