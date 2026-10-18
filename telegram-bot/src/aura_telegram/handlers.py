from __future__ import annotations

from asyncio import sleep
import base64
import binascii
from dataclasses import dataclass, field
from io import BytesIO
import logging
import re
from typing import Any
from uuid import UUID, uuid4

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PhotoSize,
    ReplyKeyboardMarkup,
    Update,
    User,
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from aura_telegram.backend import AuraBackendClient, BackendAPIError
from aura_telegram.messages import (
    backend_error_message,
    candidate_message,
    correction_value,
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


logger = logging.getLogger(__name__)
MODE_KEY = "upload_mode"
OWNED_MODE = "OWNED"
CANDIDATE_MODE = "CANDIDATE"
OWNED_ALBUMS_KEY = "owned_photo_albums"
OWNED_ALBUM_SETTLE_SECONDS = 0.8
MAX_OWNED_ALBUM_ITEMS = 10
SUGGESTION_STATE_KEY = "suggestion_state"
MAX_SUGGESTION_IMAGES = 5
WARDROBE_STATE_KEY = "wardrobe_state"
FEEDBACK_PATTERN = re.compile(
    r"^fb:(?P<match_id>[0-9a-fA-F-]{36}):(?P<feedback_type>LIKE|DISLIKE|BOUGHT|NOT_BOUGHT)$"
)
PROFILE_ACTION_PATTERN = re.compile(
    r"^rst:[yn]$"
)
SUGGESTION_PATTERN = re.compile(
    r"^(?:sug:(SAFE_EXTENSION|INTENTIONAL_CONTRAST|SURPRISE_ME|MORE|FINISH)|"
    r"sugc:(ANY|TOPS|OUTERWEAR|PANTS|ACCESSORIES|FOOTWEAR))$"
)
PREFERENCE_PATTERN = re.compile(
    r"^pref:(MENSWEAR|WOMENSWEAR|GENDER_NEUTRAL|NO_PREFERENCE):(suggestion|settings)$"
)
WARDROBE_PATTERN = re.compile(
    r"^(?:wd:[0-9a-fA-F-]{36}|wdp:[1-9][0-9]*|wde:[0-9a-fA-F-]{36}|"
    r"wdf:(?:item_name|item_type|colours|patterns|materials|textures|style_traits|"
    r"shape_traits|decorative_details):[0-9a-fA-F-]{36}|wdb|wdi|wdx|wca|"
    r"wcc:[yn]|wdr:[0-9a-fA-F-]{36}|wrr:[yn]|wra:[0-9a-fA-F-]{36}|"
    r"wrs:[yn]|wrc:[yn])$"
)


@dataclass(slots=True)
class OwnedAlbumItem:
    photo: PhotoSize
    item_name: str | None


@dataclass(slots=True)
class OwnedAlbumBatch:
    user_id: int
    display_name: str | None
    progress_message: Message
    items: list[OwnedAlbumItem] = field(default_factory=list)
    skipped_count: int = 0
    revision: int = 0
    processing: bool = False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(MODE_KEY, None)
    context.user_data.pop(WARDROBE_STATE_KEY, None)
    if update.effective_message is None:
        return
    keyboard = ReplyKeyboardMarkup(
        [
            ["/add", "/check"],
            ["/profile", "/suggestion"],
            ["/wardrobe", "/resetprofile"],
            ["/settings", "/help", "/done"],
        ],
        resize_keyboard=True,
    )
    await update.effective_message.reply_text(
        "Welcome to AURA, an AI-powered personal style assistant. I learn your "
        "visual preferences from clothes and accessories you like, then explain how a "
        "new item may fit or contrast with them.\n\n"
        "Use /add to upload 5–10 items you like. Use /check when your profile "
        "is ready and you want to evaluate another item. Use /profile to see what "
        "AURA has learned.",
        reply_markup=keyboard,
    )


async def request_suggestions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    context.user_data.pop(SUGGESTION_STATE_KEY, None)
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    display_name = user.first_name or user.username or None
    try:
        payload = await _backend_client(context).get_preferences(
            telegram_user_id=user.id,
            display_name=display_name,
        )
    except BackendAPIError as error:
        await message.reply_text(_backend_error_text(error))
        return
    preference = payload.get("fashion_presentation")
    if not isinstance(preference, str):
        await message.reply_text(
            fashion_preference_message(None, first_time=True),
            reply_markup=_fashion_preference_keyboard("suggestion"),
        )
        return
    await message.reply_text(
        suggestion_intro_message(preference),
        reply_markup=_suggestion_intent_keyboard(),
    )


async def show_settings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    try:
        payload = await _backend_client(context).get_preferences(
            telegram_user_id=user.id,
            display_name=user.first_name or user.username or None,
        )
    except BackendAPIError as error:
        await message.reply_text(_backend_error_text(error))
        return
    preference = payload.get("fashion_presentation")
    await message.reply_text(
        fashion_preference_message(preference if isinstance(preference, str) else None),
        reply_markup=_fashion_preference_keyboard("settings"),
    )


async def handle_preference_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if query is None or not isinstance(query.data, str):
        return
    match = PREFERENCE_PATTERN.fullmatch(query.data)
    if match is None:
        await query.answer("That setting is no longer valid.", show_alert=True)
        return
    preference, destination = match.groups()
    user = query.from_user
    try:
        await _backend_client(context).update_fashion_presentation(
            telegram_user_id=user.id,
            display_name=user.first_name or user.username or None,
            fashion_presentation=preference,
        )
    except BackendAPIError as error:
        await query.answer(_backend_error_text(error), show_alert=True)
        return
    await query.answer("Preference saved")
    if destination == "suggestion":
        await query.edit_message_text(
            suggestion_intro_message(preference),
            reply_markup=_suggestion_intent_keyboard(),
        )
        return
    await query.edit_message_text(
        fashion_preference_saved_message(preference),
        reply_markup=_fashion_preference_keyboard("settings"),
    )


def _fashion_preference_keyboard(destination: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Menswear",
                    callback_data=f"pref:MENSWEAR:{destination}",
                ),
                InlineKeyboardButton(
                    "Womenswear",
                    callback_data=f"pref:WOMENSWEAR:{destination}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Gender-neutral",
                    callback_data=f"pref:GENDER_NEUTRAL:{destination}",
                ),
                InlineKeyboardButton(
                    "No preference",
                    callback_data=f"pref:NO_PREFERENCE:{destination}",
                ),
            ],
        ]
    )


def _suggestion_intent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Safe Extension", callback_data="sug:SAFE_EXTENSION")],
            [
                InlineKeyboardButton(
                    "Intentional Contrast",
                    callback_data="sug:INTENTIONAL_CONTRAST",
                )
            ],
            [InlineKeyboardButton("Surprise Me", callback_data="sug:SURPRISE_ME")],
        ]
    )


async def handle_suggestion_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if query is None or not isinstance(query.data, str) or query.message is None:
        return
    if query.data.startswith("sugc:"):
        action = "CATEGORY"
        selected_category = query.data.removeprefix("sugc:")
    else:
        action = query.data.removeprefix("sug:")
        selected_category = None
    state = context.user_data.get(SUGGESTION_STATE_KEY)
    if action == "FINISH":
        context.user_data.pop(SUGGESTION_STATE_KEY, None)
        await query.answer("Suggestion session finished")
        await query.edit_message_text(suggestion_finished_message())
        return
    if action == "MORE":
        if (
            not isinstance(state, dict)
            or not isinstance(state.get("intent"), str)
            or not isinstance(state.get("category"), str)
        ):
            await query.answer(
                "This suggestion session has expired. Use /suggestion again.",
                show_alert=True,
            )
            return
        intent = state["intent"]
        category = state["category"]
        labels = state.get("labels", [])
        generated_count = state.get("generated_count", 0)
        if not isinstance(labels, list) or not isinstance(generated_count, int):
            context.user_data.pop(SUGGESTION_STATE_KEY, None)
            await query.answer("Use /suggestion to start again.", show_alert=True)
            return
        remaining = MAX_SUGGESTION_IMAGES - generated_count
        if remaining <= 0:
            await query.answer("You already generated five references.", show_alert=True)
            return
        count = min(2, remaining)
    elif action == "CATEGORY":
        if not isinstance(state, dict) or not isinstance(state.get("intent"), str):
            await query.answer(
                "This suggestion session has expired. Use /suggestion again.",
                show_alert=True,
            )
            return
        intent = state["intent"]
        category = selected_category or "ANY"
        labels = []
        generated_count = 0
        count = 3
    else:
        intent = action
        context.user_data[SUGGESTION_STATE_KEY] = {
            "intent": intent,
            "labels": [],
            "generated_count": 0,
        }
        await query.answer()
        await query.edit_message_text(
            suggestion_category_message(),
            reply_markup=_suggestion_category_keyboard(),
        )
        return

    await query.answer()
    await query.edit_message_text(
        f"Generating {count} profile-guided reference image{'s' if count != 1 else ''}..."
    )
    try:
        payload = await _backend_client(context).generate_suggestions(
            telegram_user_id=query.from_user.id,
            display_name=query.from_user.first_name or query.from_user.username or None,
            intent=intent,
            category=category,
            count=count,
            exclude_labels=[label for label in labels if isinstance(label, str)],
        )
    except BackendAPIError as error:
        logger.warning(
            "AURA backend request failed: code=%s status=%s",
            error.code,
            error.status_code,
        )
        await query.edit_message_text(_backend_error_text(error))
        return

    suggestions = payload.get("suggestions")
    if not isinstance(suggestions, list):
        await query.edit_message_text(backend_error_message("INVALID_BACKEND_RESPONSE"))
        return

    await query.edit_message_text(
        "Generation complete. Your reference images are below."
    )

    sent_labels: list[str] = []
    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            continue
        label = suggestion.get("label")
        rationale = suggestion.get("rationale")
        encoded_image = suggestion.get("image_base64")
        values = (label, rationale, encoded_image)
        if not all(isinstance(value, str) and value.strip() for value in values):
            continue
        try:
            image_data = base64.b64decode(encoded_image, validate=True)
        except (binascii.Error, ValueError):
            continue
        if not image_data:
            continue
        image_file = BytesIO(image_data)
        image_file.name = "aura-suggestion.jpg"
        await query.message.reply_photo(
            photo=image_file,
            caption=suggestion_caption(
                position=generated_count + len(sent_labels) + 1,
                label=label,
                rationale=rationale,
            ),
            parse_mode=ParseMode.HTML,
        )
        sent_labels.append(label)

    if not sent_labels:
        await query.edit_message_text(backend_error_message("INVALID_BACKEND_RESPONSE"))
        return

    labels.extend(sent_labels)
    generated_count += len(sent_labels)
    context.user_data[SUGGESTION_STATE_KEY] = {
        "intent": intent,
        "category": category,
        "labels": labels,
        "generated_count": generated_count,
    }
    reply_markup = None
    if generated_count < MAX_SUGGESTION_IMAGES:
        reply_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Generate 2 More", callback_data="sug:MORE")],
                [
                    InlineKeyboardButton(
                        "Finish Suggestions",
                        callback_data="sug:FINISH",
                    )
                ],
            ]
        )
        await query.message.reply_text(
            suggestion_controls_message(
                generated_count=generated_count,
                maximum_count=MAX_SUGGESTION_IMAGES,
            ),
            reply_markup=reply_markup,
        )
        return
    context.user_data.pop(SUGGESTION_STATE_KEY, None)
    await query.message.reply_text(
        suggestion_controls_message(
            generated_count=generated_count,
            maximum_count=MAX_SUGGESTION_IMAGES,
        )
        + "\n\n"
        + suggestion_finished_message()
    )


def _suggestion_category_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Any Category", callback_data="sugc:ANY")],
            [
                InlineKeyboardButton("Tops", callback_data="sugc:TOPS"),
                InlineKeyboardButton("Outerwear", callback_data="sugc:OUTERWEAR"),
            ],
            [
                InlineKeyboardButton("Pants", callback_data="sugc:PANTS"),
                InlineKeyboardButton("Accessories", callback_data="sugc:ACCESSORIES"),
            ],
            [InlineKeyboardButton("Footwear", callback_data="sugc:FOOTWEAR")],
        ]
    )


async def browse_wardrobe(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    context.user_data[WARDROBE_STATE_KEY] = {"page": 1}
    text, reply_markup = await _wardrobe_page_content(
        context=context,
        user=user,
        page=1,
    )
    await message.reply_text(text, reply_markup=reply_markup)


async def _wardrobe_page_content(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    user: User,
    page: int,
) -> tuple[str, InlineKeyboardMarkup | None]:
    try:
        payload = await _backend_client(context).list_wardrobe_items(
            telegram_user_id=user.id,
            display_name=user.first_name or user.username or None,
            page=page,
        )
    except BackendAPIError as error:
        return _backend_error_text(error), None
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        if page == 1:
            return "Your wardrobe is empty. Use /add to upload belongings you like.", None
        return "There are no belongings on this page.", InlineKeyboardMarkup(
            [[InlineKeyboardButton("Previous", callback_data=f"wdp:{page - 1}")]]
        )
    buttons: list[list[InlineKeyboardButton]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("item_id")
        label = item.get("label")
        if isinstance(item_id, str) and isinstance(label, str):
            buttons.append(
                [
                    InlineKeyboardButton(
                        label[:48],
                        callback_data=f"wd:{item_id}",
                    )
                ]
            )
    navigation: list[InlineKeyboardButton] = []
    if payload.get("has_previous") is True and page > 1:
        navigation.append(
            InlineKeyboardButton("Previous", callback_data=f"wdp:{page - 1}")
        )
    if payload.get("has_next") is True:
        navigation.append(InlineKeyboardButton("Next", callback_data=f"wdp:{page + 1}"))
    if navigation:
        buttons.append(navigation)
    buttons.append([InlineKeyboardButton("Close", callback_data="wdx")])
    return (
        f"Your wardrobe\n\nSelect a belonging to view its photo and analysis.\n\nPage {page}",
        InlineKeyboardMarkup(buttons),
    )


async def handle_wardrobe_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if query is None or not isinstance(query.data, str) or query.message is None:
        return
    action = query.data
    state = context.user_data.setdefault(WARDROBE_STATE_KEY, {"page": 1})
    if not isinstance(state, dict):
        state = {"page": 1}
        context.user_data[WARDROBE_STATE_KEY] = state
    user = query.from_user

    if action == "wdx":
        context.user_data.pop(WARDROBE_STATE_KEY, None)
        await query.answer("Wardrobe closed")
        await _edit_callback_message(query, "Wardrobe browser closed.")
        return
    if action == "wdb":
        page = state.get("page", 1)
        page = page if isinstance(page, int) and page > 0 else 1
        text, markup = await _wardrobe_page_content(
            context=context,
            user=user,
            page=page,
        )
        await query.answer()
        await query.message.reply_text(text, reply_markup=markup)
        return
    if action.startswith("wdp:"):
        page = int(action.removeprefix("wdp:"))
        state.clear()
        state["page"] = page
        text, markup = await _wardrobe_page_content(
            context=context,
            user=user,
            page=page,
        )
        await query.answer()
        await query.edit_message_text(text, reply_markup=markup)
        return
    if action.startswith("wd:"):
        item_id = UUID(action.removeprefix("wd:"))
        await query.answer()
        await query.edit_message_text("Loading wardrobe item…")
        try:
            client = _backend_client(context)
            detail = await client.get_wardrobe_item(
                telegram_user_id=user.id,
                display_name=user.first_name or user.username or None,
                item_id=item_id,
            )
            image_data, mime_type = await client.get_wardrobe_item_image(
                telegram_user_id=user.id,
                display_name=user.first_name or user.username or None,
                item_id=item_id,
            )
        except BackendAPIError as error:
            await query.edit_message_text(_backend_error_text(error))
            return
        state.update({"item_id": str(item_id), "stage": "view"})
        image_file = BytesIO(image_data)
        image_file.name = f"wardrobe-item.{_image_extension(mime_type)}"
        await query.edit_message_text("Wardrobe item opened below.")
        await query.message.reply_photo(
            photo=image_file,
            caption=wardrobe_item_message(detail),
            parse_mode=ParseMode.HTML,
            reply_markup=_wardrobe_item_keyboard(item_id),
        )
        return
    if action.startswith("wra:"):
        item_id = UUID(action.removeprefix("wra:"))
        state.update({"item_id": str(item_id), "stage": "confirm_reanalysis_start"})
        await query.answer()
        await _edit_callback_message(
            query,
            (
                "<b>Reanalyze Item?</b>\n\n"
                "AURA will run the latest visual-analysis pipeline on the stored photo. "
                "This uses AI credits and may produce different details.\n\n"
                "You will review the new analysis before anything changes."
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton("Start Reanalysis", callback_data="wrs:y"),
                    InlineKeyboardButton("Cancel", callback_data="wrs:n"),
                ]]
            ),
        )
        return
    if action == "wrs:n":
        await query.answer("Cancelled")
        state.update({"stage": "view"})
        await _edit_callback_message(
            query,
            "Reanalysis cancelled. No changes were made.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Back to Item", callback_data="wdi")]]
            ),
        )
        return
    if action == "wrs:y":
        try:
            item_id = UUID(str(state["item_id"]))
        except (KeyError, ValueError):
            await query.answer("This reanalysis request has expired.", show_alert=True)
            return
        await query.answer()
        await _edit_callback_message(query, "Reanalyzing the stored photo.")
        try:
            payload = await _backend_client(context).preview_item_reanalysis(
                telegram_user_id=user.id,
                display_name=user.first_name or user.username or None,
                item_id=item_id,
            )
            preview_id = UUID(str(payload["preview_id"]))
        except (BackendAPIError, KeyError, ValueError) as error:
            message = (
                _backend_error_text(error)
                if isinstance(error, BackendAPIError)
                else "AURA returned an invalid reanalysis preview. Please retry."
            )
            await _edit_callback_message(
                query,
                message,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Back to Item", callback_data="wdi")]]
                ),
            )
            return
        state.update({"preview_id": str(preview_id), "stage": "review_reanalysis"})
        await _edit_callback_message(
            query,
            reanalysis_preview_message(payload),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton("Save New Analysis", callback_data="wrc:y"),
                    InlineKeyboardButton("Discard", callback_data="wrc:n"),
                ]]
            ),
        )
        return
    if action.startswith("wrc:"):
        if state.get("stage") != "review_reanalysis":
            await query.answer("This reanalysis preview has expired.", show_alert=True)
            return
        try:
            item_id = UUID(str(state["item_id"]))
            preview_id = UUID(str(state["preview_id"]))
        except (KeyError, ValueError):
            await query.answer("This reanalysis preview has expired.", show_alert=True)
            return
        client = _backend_client(context)
        if action == "wrc:n":
            try:
                await client.discard_item_reanalysis(
                    telegram_user_id=user.id,
                    display_name=user.first_name or user.username or None,
                    item_id=item_id,
                    preview_id=preview_id,
                )
            except BackendAPIError as error:
                await query.answer(_backend_error_text(error), show_alert=True)
                return
            state.update({"stage": "view"})
            state.pop("preview_id", None)
            await query.answer("New analysis discarded")
            await _edit_callback_message(
                query,
                "New analysis discarded. Your current item and profile were unchanged.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Back to Item", callback_data="wdi")]]
                ),
            )
            return
        await query.answer()
        await _edit_callback_message(query, "Saving reanalysis and rebuilding your profile...")
        try:
            payload = await client.confirm_item_reanalysis(
                telegram_user_id=user.id,
                display_name=user.first_name or user.username or None,
                item_id=item_id,
                preview_id=preview_id,
            )
        except BackendAPIError as error:
            await _edit_callback_message(query, _backend_error_text(error))
            return
        page = state.get("page", 1)
        state.clear()
        state["page"] = page
        await _edit_callback_message(
            query,
            reanalysis_saved_message(payload),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Back to Wardrobe", callback_data="wdb")]]
            ),
        )
        return
    if action.startswith("wde:"):
        item_id = UUID(action.removeprefix("wde:"))
        state.update({"item_id": str(item_id), "stage": "choose_field"})
        await query.answer()
        await query.edit_message_caption(
            caption=(
                "Edit Item Details\n\nChoose the field you want to update. "
                "AURA will show its current value before you type a replacement."
            ),
            reply_markup=_correction_field_keyboard(item_id),
        )
        return
    if action.startswith("wdf:"):
        _, field, item_id_text = action.split(":", 2)
        try:
            client = _backend_client(context)
            options = await client.get_correction_options(
                telegram_user_id=user.id,
            )
            detail = await client.get_wardrobe_item(
                telegram_user_id=user.id,
                display_name=user.first_name or user.username or None,
                item_id=UUID(item_id_text),
            )
        except BackendAPIError as error:
            await query.answer(_backend_error_text(error), show_alert=True)
            return
        option = next((value for value in options if value.get("field") == field), None)
        if option is None:
            await query.answer("That correction field is unavailable.", show_alert=True)
            return
        features = detail.get("features")
        if not isinstance(features, dict):
            await query.answer("That item analysis is unavailable.", show_alert=True)
            return
        current_value = correction_value(features, field)
        state.update(
            {
                "item_id": item_id_text,
                "field": field,
                "current_value": current_value,
                "stage": "awaiting_value",
            }
        )
        await query.answer()
        await _edit_callback_message(
            query,
            correction_instruction_message(option, current_value),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Back to Editable Fields", callback_data="wca")]]
            ),
        )
        return
    if action in {"wca", "wcc:n"}:
        try:
            item_id = UUID(str(state["item_id"]))
        except (KeyError, ValueError):
            await query.answer("This editing session has expired.", show_alert=True)
            return
        page = state.get("page", 1)
        state.clear()
        state.update({"page": page, "item_id": str(item_id), "stage": "choose_field"})
        if action == "wcc:n":
            await query.answer("Changes discarded")
        else:
            await query.answer()
        await _edit_callback_message(
            query,
            "Edit Item Details\n\nChoose another field to update.",
            reply_markup=_correction_field_keyboard(item_id),
        )
        return
    if action == "wdi":
        try:
            item_id = UUID(str(state["item_id"]))
            client = _backend_client(context)
            detail = await client.get_wardrobe_item(
                telegram_user_id=user.id,
                display_name=user.first_name or user.username or None,
                item_id=item_id,
            )
            image: tuple[bytes, str] | None = None
            if not getattr(query.message, "photo", None):
                image = await client.get_wardrobe_item_image(
                    telegram_user_id=user.id,
                    display_name=user.first_name or user.username or None,
                    item_id=item_id,
                )
        except (KeyError, ValueError):
            await query.answer("This editing session has expired.", show_alert=True)
            return
        except BackendAPIError as error:
            await query.answer(_backend_error_text(error), show_alert=True)
            return
        state.update({"stage": "view"})
        await query.answer()
        if getattr(query.message, "photo", None):
            await query.edit_message_caption(
                caption=wardrobe_item_message(detail),
                parse_mode=ParseMode.HTML,
                reply_markup=_wardrobe_item_keyboard(item_id),
            )
        else:
            if image is None:
                await query.edit_message_text("AURA could not reopen that item photo.")
                return
            image_data, mime_type = image
            image_file = BytesIO(image_data)
            image_file.name = f"wardrobe-item.{_image_extension(mime_type)}"
            await query.edit_message_text("Item details reopened below.")
            await query.message.reply_photo(
                photo=image_file,
                caption=wardrobe_item_message(detail),
                parse_mode=ParseMode.HTML,
                reply_markup=_wardrobe_item_keyboard(item_id),
            )
        return
    if action == "wcc:y":
        if state.get("stage") != "confirm":
            await query.answer("This correction has expired.", show_alert=True)
            return
        try:
            item_id = UUID(str(state["item_id"]))
            field = str(state["field"])
            values = state["values"]
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError
        except (KeyError, ValueError):
            await query.answer("This correction has expired.", show_alert=True)
            return
        await query.answer()
        await query.edit_message_text("Saving correction and rebuilding your profile...")
        try:
            payload = await _backend_client(context).apply_item_correction(
                telegram_user_id=user.id,
                display_name=user.first_name or user.username or None,
                item_id=item_id,
                field=field,
                values=values,
            )
        except BackendAPIError as error:
            await query.edit_message_text(_backend_error_text(error))
            return
        page = state.get("page", 1)
        state.clear()
        state["page"] = page
        await query.edit_message_text(
            correction_saved_message(payload),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Back to Wardrobe", callback_data="wdb")]]
            ),
        )
        return
    if action.startswith("wdr:"):
        item_id_text = action.removeprefix("wdr:")
        state.update({"remove_item_id": item_id_text, "stage": "confirm_remove"})
        await query.answer()
        await query.edit_message_caption(
            caption=(
                "Remove this belonging from your style profile? Historical analyses and "
                "feedback remain preserved."
            ),
            reply_markup=InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton("Remove Item", callback_data="wrr:y"),
                    InlineKeyboardButton("Cancel", callback_data="wrr:n"),
                ]]
            ),
        )
        return
    if action.startswith("wrr:"):
        if action == "wrr:n":
            await query.answer("Cancelled")
            await query.edit_message_caption(caption="No changes were made to your wardrobe.")
            return
        try:
            item_id = UUID(str(state["remove_item_id"]))
        except (KeyError, ValueError):
            await query.answer("This removal has expired.", show_alert=True)
            return
        try:
            payload = await _backend_client(context).remove_profile_item(
                telegram_user_id=user.id,
                display_name=user.first_name or user.username or None,
                item_id=item_id,
            )
        except BackendAPIError as error:
            await query.answer(_backend_error_text(error), show_alert=True)
            return
        await query.answer("Belonging removed")
        await query.edit_message_caption(caption=profile_mutation_message(payload))


async def handle_correction_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    user = update.effective_user
    state = context.user_data.get(WARDROBE_STATE_KEY)
    if (
        message is None
        or user is None
        or not isinstance(state, dict)
        or state.get("stage") != "awaiting_value"
        or not isinstance(message.text, str)
    ):
        return
    try:
        item_id = UUID(str(state["item_id"]))
        field = str(state["field"])
        current_value = str(state["current_value"])
    except (KeyError, ValueError):
        context.user_data.pop(WARDROBE_STATE_KEY, None)
        await message.reply_text("This correction has expired. Use /wardrobe to start again.")
        return
    values = (
        [message.text.strip()]
        if field in {"item_name", "item_type"}
        else [value.strip() for value in message.text.split(",") if value.strip()]
    )
    try:
        payload = await _backend_client(context).preview_item_correction(
            telegram_user_id=user.id,
            display_name=user.first_name or user.username or None,
            item_id=item_id,
            field=field,
            values=values,
        )
    except BackendAPIError as error:
        if error.status_code == 422:
            await message.reply_text(
                f"That value was not accepted. {error.code}\n\n"
                "Please type another value. Your current item has not changed."
            )
        else:
            await message.reply_text(_backend_error_text(error))
        return
    state.update({"values": values, "stage": "confirm"})
    await message.reply_text(
        correction_preview_message(payload, field, current_value),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("Save Correction", callback_data="wcc:y"),
                InlineKeyboardButton("Discard Changes", callback_data="wcc:n"),
            ]]
        ),
    )


def _wardrobe_item_keyboard(item_id: UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Edit Item Details", callback_data=f"wde:{item_id}")],
            [InlineKeyboardButton("Reanalyze Item", callback_data=f"wra:{item_id}")],
            [InlineKeyboardButton("Remove Item", callback_data=f"wdr:{item_id}")],
            [InlineKeyboardButton("Back to Wardrobe", callback_data="wdb")],
            [InlineKeyboardButton("Close", callback_data="wdx")],
        ]
    )


def _correction_field_keyboard(item_id: UUID) -> InlineKeyboardMarkup:
    fields = (
        ("Item Name", "item_name"),
        ("Item Type", "item_type"),
        ("Colours", "colours"),
        ("Patterns", "patterns"),
        ("Materials", "materials"),
        ("Textures", "textures"),
        ("Style Traits", "style_traits"),
        ("Shape Traits", "shape_traits"),
        ("Decorative Details", "decorative_details"),
    )
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"wdf:{field}:{item_id}")]
        for label, field in fields
    ]
    buttons.append([InlineKeyboardButton("Back to Item", callback_data="wdi")])
    return InlineKeyboardMarkup(buttons)


async def _edit_callback_message(query: Any, text: str, **kwargs: Any) -> None:
    if getattr(query.message, "photo", None):
        await query.edit_message_caption(caption=text, **kwargs)
    else:
        await query.edit_message_text(text, **kwargs)


def _image_extension(mime_type: str) -> str:
    return {"image/png": "png", "image/webp": "webp"}.get(mime_type, "jpg")


async def add_owned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[MODE_KEY] = OWNED_MODE
    if update.effective_message is not None:
        await update.effective_message.reply_text(
            "Send photos of belongings you genuinely like. You can send one photo or "
            "a batch of up to ten photos.\n\n"
            "Photo requirements:\n"
            "- Show one primary item in each photo. Upload tops and bottoms separately.\n"
            "- Every batch photo must show a different item, not another angle.\n"
            "- Use good lighting with minimal background clutter.\n"
            "- Worn items are okay if closely cropped; avoid faces and personal details.\n\n"
            "AURA processes batch photos one at a time. Captions are optional; when "
            "omitted, AURA uses the item name identified from the image. Use /done "
            "when finished."
        )


async def check_candidate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[MODE_KEY] = CANDIDATE_MODE
    if update.effective_message is not None:
        await update.effective_message.reply_text(
            "Send a clear photo of the item you want to compare with your aesthetic profile."
        )


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(MODE_KEY, None)
    correction_cancelled = context.user_data.pop(WARDROBE_STATE_KEY, None) is not None
    if update.effective_message is not None:
        await update.effective_message.reply_text(
            (
                "Current correction cancelled. " if correction_cancelled else ""
            )
            + "Upload mode closed. Use /add for more belongings or /check for a comparison."
        )


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is not None:
        await update.effective_message.reply_text(help_message())


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    display_name = user.first_name or user.username or None
    try:
        payload = await _backend_client(context).get_profile(
            telegram_user_id=user.id,
            display_name=display_name,
        )
    except BackendAPIError as error:
        logger.warning(
            "AURA backend request failed: code=%s status=%s",
            error.code,
            error.status_code,
        )
        await message.reply_text(_backend_error_text(error))
        return
    if not payload.get("display_name"):
        payload["display_name"] = display_name or "there"
    await message.reply_text(profile_message(payload), parse_mode=ParseMode.HTML)


async def request_profile_reset(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(
        "Clear every uploaded belonging and restart your style profile? "
        "Candidate checks and feedback history will remain.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Clear profile", callback_data="rst:y"),
                    InlineKeyboardButton("Cancel", callback_data="rst:n"),
                ]
            ]
        ),
    )


async def handle_profile_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if query is None or not isinstance(query.data, str):
        return
    action = query.data
    if action == "rst:n":
        await query.answer("Cancelled")
        await query.edit_message_text("No changes were made to your style profile.")
        return

    user = query.from_user
    try:
        payload = await _backend_client(context).reset_profile(
            telegram_user_id=user.id,
            display_name=user.first_name or user.username or None,
        )
    except BackendAPIError as error:
        logger.warning(
            "AURA backend request failed: code=%s status=%s",
            error.code,
            error.status_code,
        )
        await query.answer(_backend_error_text(error), show_alert=True)
        return
    await query.answer("Profile updated")
    await query.edit_message_text(profile_mutation_message(payload))


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None or not message.photo:
        return
    mode = context.user_data.get(MODE_KEY)
    if mode not in {OWNED_MODE, CANDIDATE_MODE}:
        await message.reply_text("Choose /add or /check before sending a photo.")
        return

    if mode == OWNED_MODE and message.media_group_id:
        await _queue_owned_album(message, user, context)
        return
    if mode == CANDIDATE_MODE and message.media_group_id:
        await message.reply_text(
            "Use /check with one photo only. Albums are supported for /add batches."
        )
        return

    progress = await message.reply_text("Analyzing your photo…")
    try:
        preferred_name = message.caption.strip() if message.caption else None
        request = await _photo_request(
            photo=message.photo[-1],
            telegram_user_id=user.id,
            display_name=user.full_name,
            item_name=preferred_name,
        )
        if mode == OWNED_MODE:
            payload = await _backend_client(context).upload_owned_item(**request)
            response_text = owned_item_message(payload, preferred_name)
        else:
            payload = await _backend_client(context).upload_candidate_item(**request)
            response_text = candidate_message(payload)
            context.user_data.pop(MODE_KEY, None)
    except BackendAPIError as error:
        logger.warning(
            "AURA backend request failed: code=%s status=%s",
            error.code,
            error.status_code,
        )
        await progress.edit_text(_backend_error_text(error))
        return
    except Exception:
        reference_id = _new_reference_id()
        logger.exception(
            "Unexpected Telegram photo handling failure: reference=%s",
            reference_id,
        )
        await progress.edit_text(
            "Something went wrong while processing that photo. Please retry.\n\n"
            f"Reference: {reference_id}"
        )
        return

    if mode == CANDIDATE_MODE:
        match_id = payload.get("match_id")
        await progress.edit_text(response_text)
        if match_id:
            await message.reply_text(
                taste_feedback_message(),
                reply_markup=_taste_feedback_keyboard(str(match_id)),
            )
            await message.reply_text(
                decision_feedback_message(),
                reply_markup=_decision_feedback_keyboard(str(match_id)),
            )
    else:
        await progress.edit_text(response_text)


async def _queue_owned_album(
    message: Message,
    user: User,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    media_group_id = message.media_group_id
    if media_group_id is None or not message.photo:
        return

    albums = context.user_data.setdefault(OWNED_ALBUMS_KEY, {})
    batch = albums.get(media_group_id)
    if not isinstance(batch, OwnedAlbumBatch):
        progress_message = await message.reply_text(
            f"Batch received. Collecting up to {MAX_OWNED_ALBUM_ITEMS} photos…"
        )
        batch = OwnedAlbumBatch(
            user_id=user.id,
            display_name=user.full_name,
            progress_message=progress_message,
        )
        albums[media_group_id] = batch
    if batch.processing:
        await message.reply_text(
            "That batch is already processing. Send a new album after it finishes."
        )
        return

    if len(batch.items) < MAX_OWNED_ALBUM_ITEMS:
        batch.items.append(
            OwnedAlbumItem(
                photo=message.photo[-1],
                item_name=message.caption.strip() if message.caption else None,
            )
        )
    else:
        batch.skipped_count += 1
    batch.revision += 1
    context.application.create_task(
        _process_owned_album_after_settle(
            context=context,
            media_group_id=media_group_id,
            expected_revision=batch.revision,
        ),
        name=f"owned-album-{media_group_id}-{batch.revision}",
    )


async def _process_owned_album_after_settle(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    media_group_id: str,
    expected_revision: int,
) -> None:
    await sleep(OWNED_ALBUM_SETTLE_SECONDS)
    albums = context.user_data.get(OWNED_ALBUMS_KEY)
    if not isinstance(albums, dict):
        return
    batch = albums.get(media_group_id)
    if (
        not isinstance(batch, OwnedAlbumBatch)
        or batch.processing
        or batch.revision != expected_revision
    ):
        return

    batch.processing = True
    successful_items: list[tuple[int, str]] = []
    failures: list[tuple[int, str]] = []
    latest_payload: dict[str, Any] | None = None
    try:
        item_total = len(batch.items)
        for item_number, item in enumerate(batch.items, start=1):
            await batch.progress_message.edit_text(
                f"Analyzing batch item {item_number} of {item_total}…"
            )
            try:
                request = await _photo_request(
                    photo=item.photo,
                    telegram_user_id=batch.user_id,
                    display_name=batch.display_name,
                    item_name=item.item_name,
                )
                latest_payload = await _backend_client(context).upload_owned_item(**request)
                successful_items.append(
                    (item_number, owned_item_name(latest_payload, item.item_name))
                )
            except BackendAPIError as error:
                logger.warning(
                    "AURA batch item failed: item=%s code=%s status=%s",
                    item_number,
                    error.code,
                    error.status_code,
                )
                failures.append((item_number, _backend_error_text(error)))
            except Exception:
                logger.exception("Unexpected Telegram batch item handling failure")
                failures.append((item_number, "Unexpected processing error. Please retry."))

        await batch.progress_message.edit_text(
            owned_batch_message(
                successful_items=successful_items,
                failed_items=failures,
                skipped_count=batch.skipped_count,
                latest_payload=latest_payload,
            )
        )
    finally:
        if albums.get(media_group_id) is batch:
            albums.pop(media_group_id, None)


async def _photo_request(
    *,
    photo: PhotoSize,
    telegram_user_id: int,
    display_name: str | None,
    item_name: str | None,
) -> dict[str, Any]:
    telegram_file = await photo.get_file()
    image = bytes(await telegram_file.download_as_bytearray())
    return {
        "telegram_user_id": telegram_user_id,
        "display_name": display_name,
        "image": image,
        "filename": f"telegram-{photo.file_unique_id}.jpg",
        "item_name": item_name,
    }


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or not isinstance(query.data, str):
        return
    match = FEEDBACK_PATTERN.fullmatch(query.data)
    if match is None:
        await query.answer("That feedback action is no longer valid.", show_alert=True)
        return
    try:
        client = _backend_client(context)
        await client.submit_feedback(
            telegram_user_id=query.from_user.id,
            match_id=UUID(match.group("match_id")),
            feedback_type=match.group("feedback_type"),
        )
    except BackendAPIError as error:
        await query.answer(_backend_error_text(error), show_alert=True)
        return
    feedback_type = match.group("feedback_type")
    await query.answer("Feedback received")
    await query.edit_message_text(feedback_received_message(feedback_type))


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    reference_id = _new_reference_id()
    logger.exception(
        "Unhandled Telegram update error: reference=%s",
        reference_id,
        exc_info=context.error,
    )
    if isinstance(update, Update) and update.effective_message is not None:
        await update.effective_message.reply_text(
            "Something unexpected happened. Please try the command again.\n\n"
            f"Reference: {reference_id}"
        )


def _backend_error_text(error: BackendAPIError) -> str:
    return backend_error_message(error.code, error.reference_id)


def _new_reference_id() -> str:
    return uuid4().hex[:12].upper()


def _backend_client(context: ContextTypes.DEFAULT_TYPE) -> AuraBackendClient:
    client = context.bot_data.get("backend_client")
    if not isinstance(client, AuraBackendClient):
        raise RuntimeError("AURA backend client is not configured")
    return client


def _taste_feedback_keyboard(match_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👍 Fits my taste", callback_data=f"fb:{match_id}:LIKE"),
                InlineKeyboardButton("👎 Not my taste", callback_data=f"fb:{match_id}:DISLIKE"),
            ]
        ]
    )


def _decision_feedback_keyboard(match_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🛍 Bought it", callback_data=f"fb:{match_id}:BOUGHT"),
                InlineKeyboardButton("🚫 Passed on it", callback_data=f"fb:{match_id}:NOT_BOUGHT"),
            ]
        ]
    )
