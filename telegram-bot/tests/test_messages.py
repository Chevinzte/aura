from aura_telegram.messages import (
    backend_error_message,
    candidate_message,
    help_message,
    owned_item_message,
    profile_mutation_message,
    profile_message,
)


def test_owned_item_messages_follow_profile_status() -> None:
    assert "at least five" in owned_item_message({"profile_status": "COLLECTING"})
    assert "profile is ready" in owned_item_message({"profile_status": "READY"})
    assert "could not be refreshed" in owned_item_message({"profile_status": "REBUILD_FAILED"})


def test_owned_item_message_includes_collection_progress() -> None:
    message = owned_item_message(
        {
            "profile_status": "COLLECTING",
            "usable_item_count": 3,
            "minimum_item_count": 5,
        }
    )

    assert "Progress: 3/5 usable items" in message


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


def test_profile_message_formats_ready_profile_with_headers() -> None:
    message = profile_message(
        {
            "status": "READY",
            "display_name": "Vinz",
            "usable_item_count": 6,
            "minimum_item_count": 5,
            "profile": {
                "colours": ["cream", "black"],
                "style_traits": ["minimal", "casual"],
                "patterns": ["plain"],
                "materials": ["cotton"],
                "textures": [],
                "shape_traits": ["clean lined"],
                "decorative_details": ["minimal detail"],
                "style_influences": ["quiet luxury"],
                "summary": "Your uploaded belongings suggest a minimal profile.",
            },
        }
    )

    assert message.startswith("Hello Vinz, this is your style profile")
    assert "\n\nColours: Cream, Black\n\n" in message
    assert "Style Traits: Minimal, Casual" in message
    assert "Patterns & Materials: Plain, Cotton" in message
    assert "Shape & Details: Clean Lined, Minimal Detail" in message
    assert "Style Influences: Quiet Luxury" in message
    assert "Style Summary:" in message


def test_profile_message_reports_collecting_progress() -> None:
    message = profile_message(
        {
            "status": "COLLECTING",
            "display_name": "Vinz",
            "usable_item_count": 3,
            "minimum_item_count": 5,
        }
    )

    assert "Hello Vinz" in message
    assert "Progress: 3/5 usable items" in message
    assert "/add" in message


def test_help_lists_profile_management_commands() -> None:
    message = help_message()

    assert "/remove" in message
    assert "/resetprofile" in message


def test_profile_mutation_message_explains_rebuild_state() -> None:
    ready = profile_mutation_message(
        {
            "status": "READY",
            "usable_item_count": 5,
            "removed_item_count": 1,
        }
    )
    reset = profile_mutation_message(
        {
            "status": "COLLECTING",
            "usable_item_count": 0,
            "removed_item_count": 6,
        }
    )

    assert "rebuilt" in ready
    assert "Profile cleared" in reset
