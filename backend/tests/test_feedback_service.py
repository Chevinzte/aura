from uuid import uuid4

import pytest

from aura_backend.application.feedback import FeedbackService, FeedbackTargetNotFound
from aura_backend.domain.models import FeedbackCategory, FeedbackType


class FakeFeedbackRepository:
    def __init__(self, *, user_exists: bool = True, owns_match: bool = True) -> None:
        self.user_id = uuid4()
        self.user_exists = user_exists
        self.owns_match = owns_match
        self.saved = None

    def find_user_by_telegram_id(self, telegram_user_id: int):
        return {"id": str(self.user_id)} if self.user_exists else None

    def match_belongs_to_user(self, **_: object) -> bool:
        return self.owns_match

    def upsert_feedback(self, **kwargs: object):
        self.saved = kwargs
        return {"id": str(uuid4())}


@pytest.mark.parametrize(
    ("feedback_type", "expected_category"),
    [
        (FeedbackType.LIKE, FeedbackCategory.TASTE),
        (FeedbackType.DISLIKE, FeedbackCategory.TASTE),
        (FeedbackType.BOUGHT, FeedbackCategory.DECISION),
        (FeedbackType.NOT_BOUGHT, FeedbackCategory.DECISION),
    ],
)
def test_feedback_type_determines_category(feedback_type, expected_category) -> None:
    repository = FakeFeedbackRepository()
    match_id = uuid4()

    result = FeedbackService(repository).submit(
        telegram_user_id=123,
        match_id=match_id,
        feedback_type=feedback_type,
        note="  useful result  ",
    )

    assert result.category == expected_category
    assert result.note == "useful result"
    assert repository.saved["category"] == expected_category


def test_feedback_hides_missing_user_and_unowned_match() -> None:
    with pytest.raises(FeedbackTargetNotFound):
        FeedbackService(FakeFeedbackRepository(user_exists=False)).submit(
            telegram_user_id=123,
            match_id=uuid4(),
            feedback_type=FeedbackType.LIKE,
            note=None,
        )

    with pytest.raises(FeedbackTargetNotFound):
        FeedbackService(FakeFeedbackRepository(owns_match=False)).submit(
            telegram_user_id=123,
            match_id=uuid4(),
            feedback_type=FeedbackType.BOUGHT,
            note=None,
        )
