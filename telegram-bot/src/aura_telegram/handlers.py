from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from aura_telegram.backend import AuraBackendClient, BackendAPIError
from aura_telegram.messages import (
    backend_error_message,
    candidate_message,
    help_message,
    owned_item_message,
    profile_mutation_message,
    profile_message,
)


logger = logging.getLogger(__name__)
MODE_KEY = "upload_mode"
OWNED_MODE = "OWNED"
CANDIDATE_MODE = "CANDIDATE"
FEEDBACK_PATTERN = re.compile(
    r"^fb:(?P<match_id>[0-9a-fA-F-]{36}):(?P<feedback_type>LIKE|DISLIKE|BOUGHT|NOT_BOUGHT)$"
)
PROFILE_ACTION_PATTERN = re.compile(
    r"^(?:rm:[0-9a-fA-F-]{36}|rmc:[0-9a-fA-F-]{36}|rmx|rst:y|rst:n)$"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(MODE_KEY, None)
    if update.effective_message is None:
        return
    keyboard = ReplyKeyboardMarkup(
        [["/add", "/check"], ["/profile", "/remove"], ["/help", "/done"]],
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


async def add_owned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[MODE_KEY] = OWNED_MODE
    if update.effective_message is not None:
        await update.effective_message.reply_text(
            "Send a clear photo of one belonging you genuinely like. "
            "You can use the photo caption as its name."
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
    await message.reply_text(profile_message(payload))


async def remove_profile_item(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    try:
        payload = await _backend_client(context).list_profile_items(
            telegram_user_id=user.id,
            display_name=user.first_name or user.username or None,
        )
    except BackendAPIError as error:
        logger.warning(
            "AURA backend request failed: code=%s status=%s",
            error.code,
            error.status_code,
        )
        await message.reply_text(backend_error_message(error.code))
        return

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        await message.reply_text(
            "You do not have any uploaded belongings to remove. Use /add to begin."
        )
        return
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
        await message.reply_text("AURA could not display your uploaded belongings.")
        return
    buttons.append([InlineKeyboardButton("Cancel", callback_data="rmx")])
    await message.reply_text(
        "Choose the belonging you want to remove from your style profile:",
        reply_markup=InlineKeyboardMarkup(buttons),
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

    progress = await message.reply_text("Analyzing your photo…")
    try:
        photo = message.photo[-1]
        telegram_file = await photo.get_file()
        image = bytes(await telegram_file.download_as_bytearray())
        client = _backend_client(context)
        request: dict[str, Any] = {
            "telegram_user_id": user.id,
            "display_name": user.full_name,
            "image": image,
            "filename": f"telegram-{photo.file_unique_id}.jpg",
            "item_name": message.caption.strip() if message.caption else None,
        }
        if mode == OWNED_MODE:
            payload = await client.upload_owned_item(**request)
            response_text = owned_item_message(payload)
        else:
            payload = await client.upload_candidate_item(**request)
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
