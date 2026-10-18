import logging
import re
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request

from aura_backend.api.routes.feedback import router as feedback_router
from aura_backend.api.routes.items import router as items_router
from aura_backend.api.routes.preferences import router as preferences_router
from aura_backend.api.routes.health import router as health_router
from aura_backend.api.routes.profiles import router as profiles_router
from aura_backend.api.routes.suggestions import router as suggestions_router
from aura_backend.api.routes.wardrobe import router as wardrobe_router


logger = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def create_app() -> FastAPI:
    """Create the frontend-independent AURA API application."""
    app = FastAPI(
        title="AURA API",
        version="0.1.0",
        description="Backend API for AURA aesthetic matching.",
    )

    @app.middleware("http")
    async def add_request_reference(request: Request, call_next):
        supplied_reference = request.headers.get("X-Request-ID", "")
        reference_id = (
            supplied_reference
            if _REQUEST_ID_PATTERN.fullmatch(supplied_reference)
            else uuid4().hex[:12].upper()
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "AURA request failed: reference=%s method=%s path=%s",
                reference_id,
                request.method,
                request.url.path,
            )
            raise
        response.headers["X-Request-ID"] = reference_id
        logger.info(
            "AURA request completed: reference=%s method=%s path=%s status=%s",
            reference_id,
            request.method,
            request.url.path,
            response.status_code,
        )
        return response

    app.include_router(health_router)
    app.include_router(items_router)
    app.include_router(feedback_router)
    app.include_router(preferences_router)
    app.include_router(profiles_router)
    app.include_router(suggestions_router)
    app.include_router(wardrobe_router)
    return app


app = create_app()
