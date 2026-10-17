from __future__ import annotations

import logging

from telegram import BotCommand, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from aura_telegram.backend import AuraBackendClient
from aura_telegram.config import BotSettings, get_bot_settings
from aura_telegram.handlers import (
    FEEDBACK_PATTERN,
    PREFERENCE_PATTERN,
    PROFILE_ACTION_PATTERN,
    SUGGESTION_PATTERN,
    add_owned,
    check_candidate,
    done,
    handle_error,
    handle_feedback,
    handle_preference_action,
    handle_profile_action,
    handle_suggestion_action,
    handle_photo,
    show_help,
    show_profile,
    show_settings,
    remove_profile_item,
    request_profile_reset,
    request_suggestions,
    start,
)


def build_application(settings: BotSettings) -> Application:
    """Build the Telegram frontend without importing backend business logic."""
    backend_client = AuraBackendClient(
        base_url=str(settings.backend_url),
        timeout_seconds=settings.backend_timeout_seconds,
    )

    async def close_backend(_: Application) -> None:
        await backend_client.close()

    async def set_commands(application: Application) -> None:
        try:
            await application.bot.set_my_commands(
                [
                    BotCommand("add", "Add a belonging you like"),
                    BotCommand("check", "Check an item against your profile"),
                    BotCommand("profile", "View your style profile"),
                    BotCommand("suggestion", "Build on your style profile"),
                    BotCommand("settings", "Set suggestion fashion preference"),
                    BotCommand("remove", "Remove one uploaded belonging"),
                    BotCommand("resetprofile", "Clear and restart your profile"),
                    BotCommand("help", "Show the AURA command guide"),
                    BotCommand("done", "Exit photo-upload mode"),
                ]
            )
        except TelegramError:
            logging.getLogger(__name__).warning("Could not refresh Telegram bot commands")

    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(set_commands)
        .post_shutdown(close_backend)
        .build()
    )
    application.bot_data["backend_client"] = backend_client
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_owned))
    application.add_handler(CommandHandler("check", check_candidate))
    application.add_handler(CommandHandler("profile", show_profile))
    application.add_handler(CommandHandler("suggestion", request_suggestions))
    application.add_handler(CommandHandler("settings", show_settings))
    application.add_handler(CommandHandler("remove", remove_profile_item))
    application.add_handler(CommandHandler("resetprofile", request_profile_reset))
    application.add_handler(CommandHandler("help", show_help))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CallbackQueryHandler(handle_feedback, pattern=FEEDBACK_PATTERN))
    application.add_handler(
        CallbackQueryHandler(handle_preference_action, pattern=PREFERENCE_PATTERN)
    )
    application.add_handler(
        CallbackQueryHandler(handle_profile_action, pattern=PROFILE_ACTION_PATTERN)
    )
    application.add_handler(
        CallbackQueryHandler(handle_suggestion_action, pattern=SUGGESTION_PATTERN)
    )
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_error_handler(handle_error)
    return application


def run() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    application = build_application(get_bot_settings())
    application.run_polling(allowed_updates=Update.ALL_TYPES)
