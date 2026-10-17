from __future__ import annotations

from asyncio import sleep
import base64
import binascii
from dataclasses import dataclass, field
from io import BytesIO
import logging
import re
from typing import Any
from uuid import UUID

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
    help_message,
    owned_batch_message,
    owned_item_message,
    owned_item_name,
    profile_mutation_message,
    profile_message,
    suggestion_caption,
    suggestion_category_message,
    suggestion_intro_message,
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
FEEDBACK_PATTERN = re.compile(
    r"^fb:(?P<match_id>[0-9a-fA-F-]{36}):(?P<feedback_type>LIKE|DISLIKE|BOUGHT|NOT_BOUGHT)$"
)
PROFILE_ACTION_PATTERN = re.compile(
    r"^(?:rm:[0-9a-fA-F-]{36}|rmc:[0-9a-fA-F-]{36}|rmp:[1-9][0-9]*|"
    r"rmx|rst:y|rst:n)$"
)
SUGGESTION_PATTERN = re.compile(
    r"^(?:sug:(SAFE_EXTENSION|INTENTIONAL_CONTRAST|SURPRISE_ME|MORE)|"
    r"sugc:(ANY|TOPS|OUTERWEAR|PANTS|ACCESSORIES|FOOTWEAR))$"
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
    if update.effective_message is None:
        return
    keyboard = ReplyKeyboardMarkup(
        [
            ["/add", "/check"],
            ["/profile", "/suggestion"],
            ["/remove", "/resetprofile"],
            ["/help", "/done"],
        ],
        resize_keyboard=True,
    )
    await update.effective_message.reply_text(
        "Welcome to AURA. I learn your visual preferences from belongings you like, "
        "then explain how a new item may fit or contrast with them.\n\n"
        "Use /add to upload 5–10 belongings you like. Use /check when your profile "
        "is ready and you want to evaluate another item. Use /profile to see what "
        "AURA has learned.",
        reply_markup=keyboard,
    )


async def request_suggestions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    context.user_data.pop(SUGGESTION_STATE_KEY, None)
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(
        suggestion_intro_message(),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Safe Extension",
                        callback_data="sug:SAFE_EXTENSION",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Intentional Contrast",
                        callback_data="sug:INTENTIONAL_CONTRAST",
                    )
                ],
                [InlineKeyboardButton("Surprise Me", callback_data="sug:SURPRISE_ME")],
            ]
        ),
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
        await query.edit_message_text(backend_error_message(error.code))
        return

    suggestions = payload.get("suggestions")
    if not isinstance(suggestions, list):
        await query.edit_message_text(backend_error_message("INVALID_BACKEND_RESPONSE"))
        return

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
            [[InlineKeyboardButton("Generate 2 More", callback_data="sug:MORE")]]
        )
    await query.edit_message_text(
        f"Generated {generated_count} of {MAX_SUGGESTION_IMAGES} available references. "
        "The images remain in this chat.",
        reply_markup=reply_markup,
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
    if update.effective_message is not None:
        await update.effective_message.reply_text(
            "Upload mode closed. Use /add for more belongings or /check for a comparison."
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
        await message.reply_text(backend_error_message(error.code))
        return
    if not payload.get("display_name"):
        payload["display_name"] = display_name or "there"
    await message.reply_text(profile_message(payload), parse_mode=ParseMode.HTML)


async def remove_profile_item(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    text, reply_markup = await _remove_page_content(
        context=context,
        user=user,
        page=1,
    )
    await message.reply_text(text, reply_markup=reply_markup)


async def _remove_page_content(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    user: User,
    page: int,
) -> tuple[str, InlineKeyboardMarkup | None]:
    try:
        payload = await _backend_client(context).list_profile_items(
            telegram_user_id=user.id,
            display_name=user.first_name or user.username or None,
            page=page,
        )
    except BackendAPIError as error:
        logger.warning(
            "AURA backend request failed: code=%s status=%s",
            error.code,
            error.status_code,
        )
        return backend_error_message(error.code), None

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        if page == 1:
            return (
                "You do not have any uploaded belongings to remove. Use /add to begin.",
                None,
            )
        return (
            "There are no belongings on this page.",
            InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Previous", callback_data=f"rmp:{page - 1}")],
                    [InlineKeyboardButton("Cancel", callback_data="rmx")],
                ]
            ),
        )
    buttons = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("item_id")
        label = item.get("label")
        if isinstance(item_id, str) and isinstance(label, str):
            created_at = item.get("created_at")
            date_label = (
                f" · {created_at[:10]}"
                if isinstance(created_at, str) and len(created_at) >= 10
                else ""
            )
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{label[:38]}{date_label}",
                        callback_data=f"rm:{item_id}",
                    )
                ]
            )
    if not buttons:
        return "AURA could not display your uploaded belongings.", None
    navigation = []
    if payload.get("has_previous") is True and page > 1:
        navigation.append(
            InlineKeyboardButton("Previous", callback_data=f"rmp:{page - 1}")
        )
    if payload.get("has_next") is True:
        navigation.append(InlineKeyboardButton("Next", callback_data=f"rmp:{page + 1}"))
    if navigation:
        buttons.append(navigation)
    buttons.append([InlineKeyboardButton("Cancel", callback_data="rmx")])
    resolved_page = payload.get("page") if isinstance(payload.get("page"), int) else page
    return (
        f"Choose the belonging you want to remove from your style profile:\n\n"
        f"Page {resolved_page}",
        InlineKeyboardMarkup(buttons),
    )


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
    if action in {"rmx", "rst:n"}:
        await query.answer("Cancelled")
        await query.edit_message_text("No changes were made to your style profile.")
        return
    if action.startswith("rmp:"):
        await query.answer()
        text, reply_markup = await _remove_page_content(
            context=context,
            user=query.from_user,
            page=int(action.removeprefix("rmp:")),
        )
        await query.edit_message_text(text, reply_markup=reply_markup)
        return
    if action.startswith("rm:"):
        item_id = action.removeprefix("rm:")
        await query.answer()
        await query.edit_message_text(
            "Remove this belonging from your style profile?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Remove",
                            callback_data=f"rmc:{item_id}",
                        ),
                        InlineKeyboardButton("Cancel", callback_data="rmx"),
                    ]
                ]
            ),
        )
        return

    user = query.from_user
    try:
        client = _backend_client(context)
        if action.startswith("rmc:"):
            payload = await client.remove_profile_item(
                telegram_user_id=user.id,
                display_name=user.first_name or user.username or None,
                item_id=UUID(action.removeprefix("rmc:")),
            )
        else:
            payload = await client.reset_profile(
                telegram_user_id=user.id,
                display_name=user.first_name or user.username or None,
            )
    except BackendAPIError as error:
        logger.warning(
            "AURA backend request failed: code=%s status=%s",
            error.code,
            error.status_code,
        )
        await query.answer(backend_error_message(error.code), show_alert=True)
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
        await progress.edit_text(backend_error_message(error.code))
        return
    except Exception:
        logger.exception("Unexpected Telegram photo handling failure")
        await progress.edit_text("Something went wrong while processing that photo. Please retry.")
        return

    if mode == CANDIDATE_MODE:
        match_id = payload.get("match_id")
        reply_markup = _feedback_keyboard(str(match_id)) if match_id else None
        await progress.edit_text(response_text, reply_markup=reply_markup)
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
                failures.append((item_number, backend_error_message(error.code)))
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
    except BackendAPIError:
        await query.answer("Feedback could not be saved. Please retry.", show_alert=True)
        return
    await query.answer("Feedback saved. Thank you!")


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled Telegram update error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message is not None:
        await update.effective_message.reply_text(
            "Something unexpected happened. Please try the command again."
        )


def _backend_client(context: ContextTypes.DEFAULT_TYPE) -> AuraBackendClient:
    client = context.bot_data.get("backend_client")
    if not isinstance(client, AuraBackendClient):
        raise RuntimeError("AURA backend client is not configured")
    return client


def _feedback_keyboard(match_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👍 Fits my taste", callback_data=f"fb:{match_id}:LIKE"),
                InlineKeyboardButton("👎 Not my taste", callback_data=f"fb:{match_id}:DISLIKE"),
            ],
            [
                InlineKeyboardButton("🛍 Bought it", callback_data=f"fb:{match_id}:BOUGHT"),
                InlineKeyboardButton("Passed on it", callback_data=f"fb:{match_id}:NOT_BOUGHT"),
            ],
        ]
    )
