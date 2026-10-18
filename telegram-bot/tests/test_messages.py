from aura_telegram.messages import (
    backend_error_message,
    candidate_message,
    correction_instruction_message,
    correction_preview_message,
    correction_saved_message,
    decision_feedback_message,
    fashion_preference_message,
    fashion_preference_saved_message,
    feedback_received_message,
    help_message,
    owned_batch_message,
    owned_item_message,
    owned_item_name,
    profile_mutation_message,
    profile_message,
    reanalysis_preview_message,
    reanalysis_saved_message,
    suggestion_caption,
    suggestion_category_message,
    suggestion_controls_message,
    suggestion_finished_message,
    suggestion_intro_message,
    taste_feedback_message,
    wardrobe_item_message,
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


def test_owned_item_name_prefers_caption_then_vision_name() -> None:
    payload = {
        "features": {
            "itemName": "vision-inferred shirt",
            "itemType": {"value": "shirt"},
        }
    }

    assert owned_item_name(payload, "My favourite top") == "My favourite top"
    assert owned_item_name(payload) == "vision-inferred shirt"
    assert "vision-inferred shirt" in owned_item_message(payload)


def test_owned_batch_message_summarizes_partial_success() -> None:
    message = owned_batch_message(
        successful_items=[(1, "White shirt"), (2, "Black trousers")],
        failed_items=[(3, "That image was unusable.")],
        skipped_count=1,
        latest_payload={"usable_item_count": 4, "minimum_item_count": 5},
    )

    assert "Added: 2/3" in message
    assert "1. White shirt" in message
    assert "2. Black trousers" in message
    assert "Could not add: 1" in message
    assert "Item 3: That image was unusable." in message
    assert "beyond the ten-photo batch limit" in message
    assert "Profile progress: 4/5" in message


def test_help_message_explains_batch_size_and_optional_captions() -> None:
    message = help_message()

    assert "up to ten different items" in message
    assert "Captions are optional" in message
    assert "item name identified from the image" in message


def test_candidate_message_uses_backend_explanation_verbatim() -> None:
    explanation = "Moderate Fit. The colours align."
    assert candidate_message({"match": {"explanation": explanation}}) == explanation


def test_feedback_questions_explain_the_two_independent_signals() -> None:
    taste = taste_feedback_message()
    decision = decision_feedback_message()

    assert taste.startswith("Does this item suit your taste?")
    assert "personal style" in taste
    assert decision.startswith("What did you decide?")
    assert "return to these buttons" in decision


def test_feedback_confirmation_names_the_recorded_choice() -> None:
    assert feedback_received_message("LIKE") == (
        "✅ Feedback received\n\nTaste: Fits my taste"
    )
    assert feedback_received_message("DISLIKE").endswith("Taste: Not my taste")
    assert feedback_received_message("BOUGHT").endswith("Decision: Bought it")
    assert feedback_received_message("NOT_BOUGHT").endswith("Decision: Passed on it")


def test_profile_not_ready_error_gives_actionable_guidance() -> None:
    message = backend_error_message("PROFILE_NOT_READY")
    assert "/add" in message
    assert "five" in message


def test_pipeline_errors_have_specific_messages() -> None:
    fallback = backend_error_message("UNKNOWN_ERROR")

    assert backend_error_message("VISION_ANALYSIS_FAILED") != fallback
    assert backend_error_message("EMBEDDING_GENERATION_FAILED") != fallback
    assert backend_error_message("BACKEND_REQUEST_FAILED") != fallback


def test_operational_errors_include_reference_but_input_errors_do_not() -> None:
    operational = backend_error_message("BACKEND_UNAVAILABLE", "ABCDEF123456")
    input_error = backend_error_message("IMAGE_UNUSABLE", "ABCDEF123456")

    assert "Reference: ABCDEF123456" in operational
    assert "try again shortly" in operational
    assert "Reference:" not in input_error


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
    assert "\n\n<b>Colours:</b> Cream, Black\n\n" in message
    assert "<b>Style Traits:</b> Minimal, Casual" in message
    assert "<b>Patterns &amp; Materials:</b> Plain, Cotton" in message
    assert "<b>Shape &amp; Details:</b> Clean Lined, Minimal Detail" in message
    assert "<b>Style Influences:</b> Quiet Luxury" in message
    assert "<b>Style Summary:</b>" in message


def test_profile_message_escapes_dynamic_html() -> None:
    message = profile_message(
        {
            "status": "READY",
            "display_name": "Vinz <Admin>",
            "profile": {
                "colours": ["black & white"],
                "style_traits": [],
                "patterns": [],
                "materials": [],
                "textures": [],
                "shape_traits": [],
                "decorative_details": [],
                "style_influences": [],
                "summary": "Clean <minimal> styling.",
            },
        }
    )

    assert "Hello Vinz &lt;Admin&gt;" in message
    assert "Black &amp; White" in message
    assert "Clean &lt;minimal&gt; styling." in message


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

    assert "/remove" not in message
    assert "/resetprofile" in message
    assert "/suggestion" in message
    assert "Outerwear" in message
    assert "Accessories" in message
    assert "ten per page" in message
    assert "/settings" in message


def test_suggestion_messages_explain_scope_and_escape_html() -> None:
    intro = suggestion_intro_message("MENSWEAR")
    category = suggestion_category_message()
    caption = suggestion_caption(
        position=1,
        label="Bag <One>",
        rationale="Works with black & white.",
    )

    assert "three single-item reference images" in intro
    assert "Fashion preference: Menswear" in intro
    assert "not shopping recommendations" in intro
    assert "some suggestions may look alike" in intro
    assert "Add more varied items" in intro
    assert "one or two familiar style anchors" in intro
    assert "less familiar shape, material, detail, or accent colour" in intro
    assert "Any Category" in category
    assert "Bag &lt;One&gt;" in caption
    assert "black &amp; white" in caption


def test_suggestion_control_messages_explain_next_action() -> None:
    controls = suggestion_controls_message(generated_count=3, maximum_count=5)

    assert "Generated 3 of 5" in controls
    assert "remain in this chat" in controls
    assert "/suggestion" in suggestion_finished_message()


def test_fashion_preference_messages_explain_scope() -> None:
    prompt = fashion_preference_message(None, first_time=True)
    saved = fashion_preference_saved_message("GENDER_NEUTRAL")

    assert "does not change your style profile" in prompt
    assert "Gender-neutral" in saved
    assert "/check results" in saved


def test_wardrobe_messages_show_features_and_correction_provenance() -> None:
    message = wardrobe_item_message(
        {
            "created_at": "2026-10-17T00:00:00Z",
            "corrected_fields": ["item_name"],
            "features": {
                "itemName": "Blue shirt",
                "itemType": {"value": "shirt"},
                "colours": [{"name": "blue", "hex": "#0000FF"}],
                "styleTraits": [{"value": "casual"}],
            },
        }
    )
    preview = correction_preview_message(
        {"features": {"itemName": "Travel shirt", "itemType": {"value": "shirt"}}},
        "item_name",
        "Blue shirt",
    )
    instruction = correction_instruction_message(
        {
            "field": "materials",
            "input_hint": "Send materials separated by commas.",
            "examples": ["linen", "cotton blend"],
        },
        "Cotton",
    )

    assert "<b>Blue shirt</b>" in message
    assert "User-corrected:</b> Item Name" in message
    assert "Current Value:</b> Blue shirt" in preview
    assert "New Value:</b> Travel shirt" in preview
    assert "original AI analysis remains preserved" in preview
    assert "Current Value:</b> Cotton" in instruction
    assert "Examples You Can Enter:</b> linen | cotton blend" in instruction
    assert "replaces this entire field" in instruction
    assert "profile was rebuilt" in correction_saved_message(
        {"profile_status": "READY", "usable_item_count": 6}
    )


def test_reanalysis_messages_compare_versions_and_warn_about_corrections() -> None:
    current = {
        "itemName": "Blue shirt",
        "itemType": {"value": "shirt"},
        "colours": [{"name": "blue"}],
        "styleTraits": [{"value": "casual"}],
    }
    proposed = {
        "itemName": "Navy overshirt",
        "itemType": {"value": "overshirt"},
        "colours": [{"name": "navy"}],
        "styleTraits": [{"value": "minimal"}],
    }
    preview = reanalysis_preview_message(
        {
            "current_features": current,
            "proposed_features": proposed,
            "replaces_manual_corrections": True,
        }
    )

    assert "Current Analysis" in preview
    assert "Name: Blue shirt" in preview
    assert "New Analysis" in preview
    assert "Name: Navy overshirt" in preview
    assert "replaces the item's current manual corrections" in preview
    assert len(preview) <= 1024
    assert "profile was rebuilt" in reanalysis_saved_message(
        {"profile_status": "READY", "usable_item_count": 6}
    )


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
