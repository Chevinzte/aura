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
            "Send another photo, use /done, or use /check to evaluate something new."
        )
    if profile_status == "REBUILD_FAILED":
        return (
            f"Item added: {item_name}. Your profile could not be refreshed right now. "
            "You can continue, and AURA will retry when another belonging is added."
        )
    progress = (
        f" Progress: {item_count}/{minimum_items} usable items."
        if isinstance(item_count, int)
        else ""
    )
    return (
        f"Item added: {item_name}. Keep sending belongings you genuinely like; AURA "
        "needs at least "
        f"five usable items to build your profile.{progress} Send another photo or use /done."
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
        "/check — Compare a new item with your current style profile.\n\n"
        "/profile — See what AURA has learned from your uploaded belongings.\n\n"
        "/remove — Browse uploaded belongings ten per page and remove one from your "
        "profile after confirmation.\n\n"
        "/resetprofile — Clear all uploaded belongings and restart your profile.\n\n"
        "/done — Exit the current photo-upload mode."
    )


def suggestion_intro_message() -> str:
    return (
        "How should AURA build on your style profile?\n\n"
        "Safe Extension stays close to your established preferences.\n\n"
        "Intentional Contrast adds one controlled difference while keeping the item "
        "coherent with your profile.\n\n"
        "Surprise Me explores a tasteful variation.\n\n"
        "After choosing a direction, choose a wardrobe category or Any Category. "
        "AURA will generate three single-item reference images. You can then request "
        "two more. These are inspiration, not shopping recommendations."
    )


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


def backend_error_message(code: str) -> str:
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
        "IMAGE_GENERATION_FAILED": (
            "AURA could not generate reference images right now. Please retry shortly."
        ),
        "OWNED_ITEM_NOT_FOUND": (
            "That belonging is no longer available in your profile. Use /remove to refresh the list."
        ),
    }
    return messages.get(code, "Something went wrong while contacting AURA. Please try again.")
