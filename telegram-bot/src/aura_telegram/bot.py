from __future__ import annotations

import logging

from telegram import Update
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
    add_owned,
    check_candidate,
    done,
    handle_error,
    handle_feedback,
    handle_photo,
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

    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_shutdown(close_backend)
        .build()
    )
    application.bot_data["backend_client"] = backend_client
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_owned))
    application.add_handler(CommandHandler("check", check_candidate))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CallbackQueryHandler(handle_feedback, pattern=FEEDBACK_PATTERN))
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
