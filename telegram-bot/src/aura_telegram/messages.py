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
        "PROFILE_INCOMPATIBLE": (
            "Your profile needs to be refreshed before this item can be compared. "
            "Try adding another belonging with /add."
        ),
    }
    return messages.get(code, "Something went wrong while contacting AURA. Please try again.")
