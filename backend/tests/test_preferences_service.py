from uuid import uuid4

from aura_backend.application.preferences import (
    FashionPresentation,
    PreferenceService,
)


class FakeRepository:
    def __init__(self) -> None:
        self.user_id = uuid4()
        self.presentation: str | None = None

    def find_or_create_user(self, *_: object) -> dict[str, object]:
        return {
            "id": str(self.user_id),
            "fashion_presentation": self.presentation,
        }

    def update_user_fashion_presentation(
        self,
        *,
        user_id,
        fashion_presentation: FashionPresentation,
    ) -> dict[str, object]:
        assert user_id == self.user_id
        self.presentation = fashion_presentation.value
        return {
            "id": str(self.user_id),
            "fashion_presentation": self.presentation,
        }


def test_preference_service_reads_unconfigured_user() -> None:
    preferences = PreferenceService(FakeRepository()).get(
        telegram_user_id=123,
        display_name="Vinz",
    )

    assert preferences.fashion_presentation is None


def test_preference_service_saves_fashion_presentation() -> None:
    repository = FakeRepository()
    preferences = PreferenceService(repository).set_fashion_presentation(
        telegram_user_id=123,
        display_name="Vinz",
        fashion_presentation=FashionPresentation.MENSWEAR,
    )

    assert preferences.fashion_presentation == FashionPresentation.MENSWEAR
    assert repository.presentation == "MENSWEAR"
