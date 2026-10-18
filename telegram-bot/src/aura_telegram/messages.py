from __future__ import annotations

from html import escape
from typing import Any


def owned_item_name(
    payload: dict[str, Any],
    preferred_name: str | None = None,
) -> str:
    if isinstance(preferred_name, str) and preferred_name.strip():
        return preferred_name.strip()[:80]

    features = payload.get("features")
    if isinstance(features, dict):
        inferred_name = features.get("itemName") or features.get("item_name")
        if isinstance(inferred_name, str) and inferred_name.strip():
            return inferred_name.strip()[:80]

        item_type = features.get("itemType") or features.get("item_type")
        if isinstance(item_type, dict):
            type_value = item_type.get("value")
            if isinstance(type_value, str) and type_value.strip():
                return type_value.replace("_", " ").strip().title()[:80]

    return "Belonging"


def owned_item_message(
    payload: dict[str, Any],
    preferred_name: str | None = None,
) -> str:
    profile_status = payload.get("profile_status")
    item_count = payload.get("usable_item_count")
    minimum_items = payload.get("minimum_item_count", 5)
    item_name = owned_item_name(payload, preferred_name)
    if profile_status == "READY":
        return (
            f"Item added: {item_name}. Your aesthetic profile is ready and now includes "
            f"{item_count or minimum_items} belongings.\n\n"
            "Add mode is still active. Send another photo or album, or use /done."
        )
    if profile_status == "REBUILD_FAILED":
        return (
            f"Item added: {item_name}. Your profile could not be refreshed right now. "
            "You can continue, and AURA will retry when another belonging is added.\n\n"
            "Add mode is still active. Send another photo or album, or use /done."
        )
    progress = (
        f" Progress: {item_count}/{minimum_items} usable items."
        if isinstance(item_count, int)
        else ""
    )
    return (
        f"Item added: {item_name}. Keep sending belongings you genuinely like; AURA "
        "needs at least "
        f"five usable items to build your profile.{progress}\n\n"
        "Add mode is still active. Send another photo or album, or use /done."
    )


def owned_batch_message(
    *,
    successful_items: list[tuple[int, str]],
    failed_items: list[tuple[int, str]],
    skipped_count: int,
    latest_payload: dict[str, Any] | None,
) -> str:
    processed_count = len(successful_items) + len(failed_items)
    lines = [
        "Batch complete.",
        f"Added: {len(successful_items)}/{processed_count}",
    ]
    lines.extend(
        f"{item_number}. {item_name}"
        for item_number, item_name in successful_items
    )
    if failed_items:
        lines.append(f"Could not add: {len(failed_items)}")
        lines.extend(
            f"- Item {item_number}: {message}"
            for item_number, message in failed_items
        )
    if skipped_count:
        lines.append(
            f"Skipped: {skipped_count} photo(s) beyond the ten-photo batch limit."
        )

    if isinstance(latest_payload, dict):
        item_count = latest_payload.get("usable_item_count")
        minimum_items = latest_payload.get("minimum_item_count", 5)
        if isinstance(item_count, int):
            lines.append(f"Profile progress: {item_count}/{minimum_items} usable items")

    lines.append("Add mode is still active. Send another photo or album, or use /done.")
    return "\n\n".join(lines)


def help_message() -> str:
    return (
        "AURA command guide\n\n"
        "/suggestion - Generate wardrobe-building reference ideas from your ready "
        "style profile. Choose Any Category, Tops, Outerwear, Pants, Accessories, "
        "or Footwear. AURA sends three AI-generated item images, with an option to "
        "generate two more.\n\n"
        "/add — Upload belongings you genuinely like. Send one photo or an album of "
        "up to ten different items. Each clear, well-lit photo must show one primary "
        "item. Captions are optional; AURA uses the item name identified from the "
        "image when omitted.\n\n"
        "/check — Compare new items with your current style profile. Send one photo "
        "or an album of up to ten different items, then use /done when finished.\n\n"
        "/profile — See what AURA has learned from your uploaded belongings.\n\n"
        "/wardrobe — Browse uploaded belongings ten per page with their stored photos. "
        "Use Edit Item Details to view current values, type corrections, and preview "
        "changes before saving, or remove an item from your profile.\n\n"
        "/settings — Choose whether generated clothing ideas should use menswear, "
        "womenswear, gender-neutral fashion, or no presentation preference.\n\n"
        "/resetprofile — Clear all uploaded belongings and restart your profile.\n\n"
        "/done — Exit the current /add or /check photo mode."
    )


def suggestion_intro_message(fashion_presentation: str | None = None) -> str:
    preference = fashion_presentation_label(fashion_presentation)
    return (
        f"Fashion preference: {preference}. Change it anytime with /settings.\n\n"
        "How should AURA build on your style profile?\n\n"
        "Safe Extension stays close to your established preferences.\n\n"
        "Intentional Contrast adds one controlled difference while keeping the item "
        "coherent with your profile.\n\n"
        "Surprise Me keeps one or two familiar style anchors while exploring a less "
        "familiar shape, material, detail, or accent colour.\n\n"
        "Please note: AURA creates ideas from your current style profile. If your "
        "profile has only a few items or similar belongings, some suggestions may "
        "look alike. Add more varied items to broaden AURA's understanding of your "
        "preferences.\n\n"
        "After choosing a direction, choose a wardrobe category or Any Category. "
        "AURA will generate three single-item reference images. You can then request "
        "two more. These are inspiration, not shopping recommendations."
    )


def fashion_preference_message(
    fashion_presentation: str | None,
    *,
    first_time: bool = False,
) -> str:
    if first_time:
        return (
            "Before generating clothing ideas, choose the fashion presentation AURA "
            "should use. This does not change your style profile or /check results."
        )
    return (
        f"Fashion preference: {fashion_presentation_label(fashion_presentation)}\n\n"
        "Choose the presentation AURA should use for generated clothing suggestions. "
        "You can change it at any time."
    )


def fashion_preference_saved_message(fashion_presentation: str) -> str:
    return (
        f"Fashion preference saved: {fashion_presentation_label(fashion_presentation)}.\n\n"
        "AURA will use this for future generated clothing ideas. It does not change "
        "your style profile or /check results."
    )


def fashion_presentation_label(value: str | None) -> str:
    return {
        "MENSWEAR": "Menswear",
        "WOMENSWEAR": "Womenswear",
        "GENDER_NEUTRAL": "Gender-neutral",
        "NO_PREFERENCE": "No preference",
    }.get(value or "", "Not set")


def suggestion_category_message() -> str:
    return (
        "Choose what kind of item AURA should suggest. Any Category lets AURA select "
        "across your wardrobe."
    )


def suggestion_caption(
    *,
    position: int,
    label: str,
    rationale: str,
) -> str:
    return (
        f"<b>Suggestion {position}: {escape(label.strip())}</b>\n\n"
        f"<b>Why:</b> {escape(rationale.strip())}\n\n"
        "AI-generated reference image. It is not a specific product or retailer listing."
    )


def suggestion_controls_message(*, generated_count: int, maximum_count: int) -> str:
    return (
        f"Generated {generated_count} of {maximum_count} available references. "
        "The images remain in this chat."
    )


def suggestion_finished_message() -> str:
    return (
        "Suggestion session finished. Use /suggestion whenever you want more ideas."
    )


def wardrobe_item_message(payload: dict[str, Any]) -> str:
    features = payload.get("features")
    if not isinstance(features, dict):
        return "AURA could not display this belonging's analysis."
    sections = [
        f"<b>{escape(_feature_text(features, 'itemName', 'item_name') or 'Belonging')}</b>",
        f"<b>Item Type:</b> {escape(_item_type_text(features))}",
    ]
    colours = features.get("colours")
    if isinstance(colours, list):
        colour_values = [
            f"{str(colour.get('name')).title()} ({str(colour.get('hex')).upper()})"
            for colour in colours[:4]
            if isinstance(colour, dict) and colour.get("name") and colour.get("hex")
        ]
        if colour_values:
            sections.append(f"<b>Colours:</b> {escape(', '.join(colour_values))}")
    for label, camel_key, snake_key in (
        ("Style Traits", "styleTraits", "style_traits"),
        ("Patterns", "patterns", "patterns"),
        ("Materials", "materials", "materials"),
        ("Textures", "textures", "textures"),
        ("Shape Traits", "shapeTraits", "shape_traits"),
        ("Details", "decorativeDetails", "decorative_details"),
    ):
        values = _observation_values(features.get(camel_key, features.get(snake_key)))
        if values:
            sections.append(f"<b>{label}:</b> {escape(', '.join(values))}")
    corrected_fields = payload.get("corrected_fields")
    if isinstance(corrected_fields, list) and corrected_fields:
        labels = [correction_field_label(str(value)) for value in corrected_fields]
        sections.append(f"<b>User-corrected:</b> {escape(', '.join(labels))}")
    if payload.get("revision_kind") == "AI_REANALYSIS":
        sections.append("<b>Analysis:</b> User-confirmed reanalysis")
    created_at = payload.get("created_at")
    if isinstance(created_at, str) and len(created_at) >= 10:
        sections.append(f"<b>Added:</b> {escape(created_at[:10])}")
    return "\n\n".join(sections)


def correction_field_label(field: str) -> str:
    return {
        "item_name": "Item Name",
        "item_type": "Item Type",
        "colours": "Colours",
        "patterns": "Patterns",
        "materials": "Materials",
        "textures": "Textures",
        "style_traits": "Style Traits",
        "shape_traits": "Shape Traits",
        "decorative_details": "Decorative Details",
    }.get(field, field.replace("_", " ").title())


def correction_instruction_message(
    option: dict[str, Any],
    current_value: str,
) -> str:
    field = str(option.get("field", ""))
    hint = str(option.get("input_hint", "Send the corrected value."))
    examples = option.get("examples")
    sections = [
        f"Editing <b>{escape(correction_field_label(field))}</b>",
        f"<b>Current Value:</b> {escape(current_value)}",
        escape(hint),
    ]
    if isinstance(examples, list) and examples:
        display = " | ".join(str(value) for value in examples)
        sections.append(f"<b>Examples You Can Enter:</b> {escape(display)}")
    if field not in {"item_name", "item_type"}:
        sections.append(
            "Your entry replaces this entire field. Include any current values you "
            "want to keep."
        )
    sections.append("Type your replacement value below.")
    return "\n\n".join(sections)


def correction_preview_message(
    payload: dict[str, Any],
    field: str,
    current_value: str,
) -> str:
    features = payload.get("features")
    if not isinstance(features, dict):
        return "AURA could not preview this correction."
    new_value = correction_value(features, field)
    return (
        f"<b>Confirm {escape(correction_field_label(field))} Change</b>\n\n"
        f"<b>Current Value:</b> {escape(current_value)}\n\n"
        f"<b>New Value:</b> {escape(new_value)}\n\n"
        "Saving creates a new correction version and rebuilds your profile. "
        "The original AI analysis remains preserved."
    )


def correction_value(features: dict[str, Any], field: str) -> str:
    if field == "item_name":
        return _feature_text(features, "itemName", "item_name") or "Not recorded"
    if field == "item_type":
        return _item_type_text(features)
    if field == "colours":
        colours = features.get("colours")
        if isinstance(colours, list):
            values = [
                str(colour.get("name")).replace("_", " ").title()
                for colour in colours
                if isinstance(colour, dict) and colour.get("name")
            ]
            return ", ".join(values) or "Not recorded"
        return "Not recorded"
    key_map = {
        "patterns": ("patterns", "patterns"),
        "materials": ("materials", "materials"),
        "textures": ("textures", "textures"),
        "style_traits": ("styleTraits", "style_traits"),
        "shape_traits": ("shapeTraits", "shape_traits"),
        "decorative_details": ("decorativeDetails", "decorative_details"),
    }
    camel_key, snake_key = key_map.get(field, (field, field))
    values = _observation_values(features.get(camel_key, features.get(snake_key)))
    return ", ".join(values) or "Not recorded"


def correction_saved_message(payload: dict[str, Any]) -> str:
    status = payload.get("profile_status")
    item_count = payload.get("usable_item_count")
    if status == "READY":
        return (
            "Correction saved. Your style profile was rebuilt from "
            f"{item_count} usable belongings."
        )
    return (
        "Correction saved. AURA preserved the updated item while your profile "
        "continues collecting enough usable belongings."
    )


def reanalysis_preview_message(payload: dict[str, Any]) -> str:
    current = payload.get("current_features")
    proposed = payload.get("proposed_features")
    if not isinstance(current, dict) or not isinstance(proposed, dict):
        return "AURA could not display the reanalysis preview."
    sections = [
        "<b>Review Reanalysis</b>",
        _reanalysis_feature_summary("Current Analysis", current),
        _reanalysis_feature_summary("New Analysis", proposed),
        (
            "Saving uses the new analysis to rebuild your profile. The previous "
            "analysis remains preserved."
        ),
    ]
    if payload.get("replaces_manual_corrections"):
        sections.append(
            "<b>Important:</b> Saving replaces the item's current manual corrections."
        )
    return "\n\n".join(sections)


def reanalysis_saved_message(payload: dict[str, Any]) -> str:
    item_count = payload.get("usable_item_count")
    if payload.get("profile_status") == "READY":
        return (
            "Reanalysis saved. Your style profile was rebuilt from "
            f"{item_count} usable belongings."
        )
    return (
        "Reanalysis saved. AURA updated the item while your profile continues "
        "collecting enough usable belongings."
    )


def _reanalysis_feature_summary(label: str, features: dict[str, Any]) -> str:
    values = [
        "Name: "
        + _short_preview_value(
            _feature_text(features, "itemName", "item_name") or "Not recorded",
            56,
        ),
        f"Type: {_short_preview_value(_item_type_text(features), 40)}",
    ]
    colours = correction_value(features, "colours")
    if colours != "Not recorded":
        values.append(f"Colours: {_short_preview_value(colours, 64)}")
    for field, display_label in (
        ("style_traits", "Style"),
        ("materials", "Materials"),
        ("shape_traits", "Shape"),
    ):
        value = correction_value(features, field)
        if value != "Not recorded":
            values.append(f"{display_label}: {_short_preview_value(value, 48)}")
    return f"<b>{escape(label)}:</b>\n" + "\n".join(escape(value) for value in values)


def _short_preview_value(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."


def profile_mutation_message(payload: dict[str, Any]) -> str:
    status = payload.get("status")
    item_count = payload.get("usable_item_count", 0)
    minimum_items = payload.get("minimum_item_count", 5)
    removed_count = payload.get("removed_item_count", 0)

    if removed_count > 1:
        return (
            f"Profile cleared. {removed_count} uploaded belongings were removed.\n\n"
            f"Progress: 0/{minimum_items} usable items. Use /add when you are ready "
            "to build a new profile."
        )
    if removed_count == 0:
        return (
            "Your profile was already empty. Use /add to begin building a new profile."
        )
    if status == "READY":
        return (
            f"Belonging removed. Your profile was rebuilt from the remaining "
            f"{item_count} usable items."
        )
    if status == "REBUILD_FAILED":
        return (
            "Belonging removed, but AURA could not refresh your profile right now. "
            "Add another belonging with /add to retry."
        )
    return (
        f"Belonging removed. Your profile now has {item_count}/{minimum_items} usable "
        "items. Use /add to make it ready again."
    )


def candidate_message(payload: dict[str, Any]) -> str:
    match = payload.get("match")
    if not isinstance(match, dict):
        return "Your item was analyzed, but the match explanation was unavailable."
    explanation = match.get("explanation")
    if isinstance(explanation, str) and explanation.strip():
        return explanation.strip()
    classification = str(match.get("classification", "UNCERTAIN")).replace("_", " ").title()
    return f"{classification}. Based on your uploaded belongings, this result is subjective guidance."


def candidate_mode_reminder() -> str:
    return "Check mode is still active. Send another photo or album, or use /done."


def candidate_batch_message(
    *,
    successful_count: int,
    failed_count: int,
    skipped_count: int,
) -> str:
    processed_count = successful_count + failed_count
    lines = ["Batch check complete.", f"Checked: {successful_count}/{processed_count}"]
    if failed_count:
        lines.append(f"Could not check: {failed_count}")
    if skipped_count:
        lines.append(
            f"Skipped: {skipped_count} photo(s) beyond the ten-photo batch limit."
        )
    return "\n\n".join(lines)


def taste_feedback_message() -> str:
    return (
        "Does this item suit your taste?\n\n"
        "Choose the option that best reflects your personal style."
    )


def decision_feedback_message() -> str:
    return (
        "What did you decide?\n\n"
        "You can answer now or return to these buttons after making your decision."
    )


def feedback_received_message(feedback_type: str) -> str:
    labels = {
        "LIKE": ("Taste", "Fits my taste"),
        "DISLIKE": ("Taste", "Not my taste"),
        "BOUGHT": ("Decision", "Bought it"),
        "NOT_BOUGHT": ("Decision", "Passed on it"),
    }
    category, choice = labels[feedback_type]
    return f"✅ Feedback received\n\n{category}: {choice}"


def profile_message(payload: dict[str, Any]) -> str:
    name = payload.get("display_name")
    greeting_name = escape(name.strip()) if isinstance(name, str) and name.strip() else "there"
    status = payload.get("status")
    item_count = payload.get("usable_item_count", 0)
    minimum_items = payload.get("minimum_item_count", 5)

    if status == "COLLECTING":
        return (
            f"Hello {greeting_name}, your style profile is still learning.\n\n"
            f"Progress: {item_count}/{minimum_items} usable items\n\n"
            "Use /add to upload more belongings you genuinely like."
        )
    if status == "UNAVAILABLE":
        return (
            f"Hello {greeting_name}, AURA has enough items but your style profile "
            "is not available right now. Add another item with /add to retry the refresh."
        )

    profile = payload.get("profile")
    if status != "READY" or not isinstance(profile, dict):
        return (
            "Your style profile could not be displayed right now. "
            "Please try again shortly."
        )

    sections = [f"Hello {greeting_name}, this is your style profile"]
    _append_profile_section(sections, "Colours", profile.get("colours"))
    _append_profile_section(sections, "Style Traits", profile.get("style_traits"))
    _append_profile_section(
        sections,
        "Patterns & Materials",
        _combined_values(
            profile.get("patterns"),
            profile.get("materials"),
            profile.get("textures"),
        ),
    )
    _append_profile_section(
        sections,
        "Shape & Details",
        _combined_values(
            profile.get("shape_traits"),
            profile.get("decorative_details"),
        ),
    )
    _append_profile_section(
        sections,
        "Style Influences",
        profile.get("style_influences"),
    )
    summary = profile.get("summary")
    if isinstance(summary, str) and summary.strip():
        sections.append(f"<b>Style Summary:</b> {escape(summary.strip())}")
    sections.append(
        "This profile reflects your uploaded belongings and may evolve as you add more."
    )
    return "\n\n".join(sections)


def _append_profile_section(sections: list[str], label: str, values: object) -> None:
    formatted = _display_values(values)
    if formatted:
        sections.append(
            f"<b>{escape(label)}:</b> {', '.join(escape(value) for value in formatted)}"
        )


def _combined_values(*groups: object) -> list[str]:
    values: list[str] = []
    for group in groups:
        for value in _display_values(group):
            if value not in values:
                values.append(value)
    return values


def _display_values(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [
        value.replace("_", " ").strip().title()
        for value in values
        if isinstance(value, str) and value.strip()
    ]


def backend_error_message(code: str, reference_id: str | None = None) -> str:
    messages = {
        "PROFILE_NOT_READY": (
            "Your aesthetic profile is not ready yet. Use /add and upload at least five "
            "belongings you genuinely like first."
        ),
        "IMAGE_UNUSABLE": (
            "I could not identify one clear item. Try another photo with one item in focus, "
            "good lighting, and less background clutter."
        ),
        "IMAGE_TOO_LARGE": "That image is too large. Please send a smaller photo.",
        "IMAGE_TOO_SMALL": "That image is too small. Please send a clearer, larger photo.",
        "UNSUPPORTED_IMAGE_TYPE": "Please send the image as a Telegram photo.",
        "INVALID_IMAGE": "That image could not be read safely. Please try another photo.",
        "BACKEND_UNAVAILABLE": "AURA is temporarily unavailable. Please try again shortly.",
        "BACKEND_AUTHENTICATION_FAILED": (
            "AURA's services could not authenticate with each other. Please contact "
            "the administrator rather than retrying this command."
        ),
        "ITEM_PROCESSING_UNAVAILABLE": "AURA could not process that item right now. Please retry.",
        "CANDIDATE_PROCESSING_UNAVAILABLE": (
            "AURA could not finish that comparison right now. Please retry."
        ),
        "VISION_ANALYSIS_FAILED": (
            "AURA's visual analysis service could not process that photo right now. "
            "Please retry shortly."
        ),
        "EMBEDDING_GENERATION_FAILED": (
            "AURA analyzed the photo but could not finish its aesthetic representation. "
            "Please retry shortly."
        ),
        "INVALID_BACKEND_RESPONSE": (
            "AURA returned an unexpected response. Please retry shortly."
        ),
        "BACKEND_REQUEST_FAILED": (
            "AURA's backend could not complete that request. Please retry shortly."
        ),
        "PROFILE_INCOMPATIBLE": (
            "Your profile needs to be refreshed before this item can be compared. "
            "Try adding another belonging with /add."
        ),
        "PROFILE_READ_UNAVAILABLE": (
            "AURA could not load your style profile right now. Please try /profile again shortly."
        ),
        "PROFILE_MANAGEMENT_UNAVAILABLE": (
            "AURA could not update your style profile right now. Please try again shortly."
        ),
        "SUGGESTION_PROCESSING_UNAVAILABLE": (
            "AURA could not prepare suggestions from your profile right now. Please retry."
        ),
        "PREFERENCES_UNAVAILABLE": (
            "AURA could not load or save your settings right now. Please retry shortly."
        ),
        "IMAGE_GENERATION_FAILED": (
            "AURA could not generate reference images right now. Please retry shortly."
        ),
        "OWNED_ITEM_NOT_FOUND": (
            "That belonging is no longer available in your profile. Use /wardrobe to refresh the list."
        ),
        "WARDROBE_ITEM_NOT_FOUND": (
            "That belonging is no longer available. Use /wardrobe to refresh the list."
        ),
        "WARDROBE_UNAVAILABLE": (
            "AURA could not load your wardrobe right now. Please retry shortly."
        ),
        "WARDROBE_CORRECTION_UNAVAILABLE": (
            "AURA could not safely apply that correction. Your previous analysis and "
            "profile were kept. Please retry."
        ),
        "WARDROBE_REANALYSIS_UNAVAILABLE": (
            "AURA could not safely reanalyze that item. The current analysis and "
            "profile were kept. Please retry shortly."
        ),
    }
    message = messages.get(
        code,
        "Something went wrong while contacting AURA. Please try the command again.",
    )
    reference_codes = {
        "BACKEND_UNAVAILABLE",
        "BACKEND_AUTHENTICATION_FAILED",
        "ITEM_PROCESSING_UNAVAILABLE",
        "CANDIDATE_PROCESSING_UNAVAILABLE",
        "VISION_ANALYSIS_FAILED",
        "EMBEDDING_GENERATION_FAILED",
        "INVALID_BACKEND_RESPONSE",
        "BACKEND_REQUEST_FAILED",
        "PROFILE_READ_UNAVAILABLE",
        "PROFILE_MANAGEMENT_UNAVAILABLE",
        "SUGGESTION_PROCESSING_UNAVAILABLE",
        "PREFERENCES_UNAVAILABLE",
        "IMAGE_GENERATION_FAILED",
        "WARDROBE_UNAVAILABLE",
        "WARDROBE_CORRECTION_UNAVAILABLE",
        "WARDROBE_REANALYSIS_UNAVAILABLE",
    }
    if reference_id and (code in reference_codes or code not in messages):
        return f"{message}\n\nReference: {reference_id}"
    return message


def _feature_text(features: dict[str, Any], camel_key: str, snake_key: str) -> str:
    value = features.get(camel_key, features.get(snake_key))
    return str(value).strip() if isinstance(value, str) else ""


def _item_type_text(features: dict[str, Any]) -> str:
    item_type = features.get("itemType", features.get("item_type"))
    if isinstance(item_type, dict):
        value = item_type.get("value")
        if isinstance(value, str) and value.strip():
            return value.replace("_", " ").title()
    return "Unknown"


def _observation_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(item["value"]).replace("_", " ").title()
        for item in value[:5]
        if isinstance(item, dict) and item.get("value")
    ]
