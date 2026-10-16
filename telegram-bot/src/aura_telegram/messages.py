from __future__ import annotations

from typing import Any


def owned_item_message(payload: dict[str, Any]) -> str:
    profile_status = payload.get("profile_status")
    if profile_status == "READY":
        return (
            "Item added. Your aesthetic profile is ready and now includes this belonging.\n\n"
            "Send another photo, use /done, or use /check to evaluate something new."
        )
    if profile_status == "REBUILD_FAILED":
        return (
            "Item added, but your profile could not be refreshed right now. "
            "You can continue, and AURA will retry when another belonging is added."
        )
    return (
        "Item added. Keep sending belongings you genuinely like; AURA needs at least "
        "five usable items to build your profile. Send another photo or use /done."
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
    greeting_name = name.strip() if isinstance(name, str) and name.strip() else "there"
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
        sections.append(f"Style Summary: {summary.strip()}")
    sections.append(
        "This profile reflects your uploaded belongings and may evolve as you add more."
    )
    return "\n\n".join(sections)


def _append_profile_section(sections: list[str], label: str, values: object) -> None:
    formatted = _display_values(values)
    if formatted:
        sections.append(f"{label}: {', '.join(formatted)}")


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
    }
    return messages.get(code, "Something went wrong while contacting AURA. Please try again.")
