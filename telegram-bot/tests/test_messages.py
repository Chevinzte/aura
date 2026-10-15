from aura_telegram.messages import backend_error_message, candidate_message, owned_item_message


def test_owned_item_messages_follow_profile_status() -> None:
    assert "at least five" in owned_item_message({"profile_status": "COLLECTING"})
    assert "profile is ready" in owned_item_message({"profile_status": "READY"})
    assert "could not be refreshed" in owned_item_message({"profile_status": "REBUILD_FAILED"})


def test_candidate_message_uses_backend_explanation_verbatim() -> None:
    explanation = "Moderate Fit. The colours align."
    assert candidate_message({"match": {"explanation": explanation}}) == explanation


def test_profile_not_ready_error_gives_actionable_guidance() -> None:
    message = backend_error_message("PROFILE_NOT_READY")
    assert "/add" in message
    assert "five" in message


def test_pipeline_errors_have_specific_messages() -> None:
    fallback = backend_error_message("UNKNOWN_ERROR")

    assert backend_error_message("VISION_ANALYSIS_FAILED") != fallback
    assert backend_error_message("EMBEDDING_GENERATION_FAILED") != fallback
    assert backend_error_message("BACKEND_REQUEST_FAILED") != fallback
