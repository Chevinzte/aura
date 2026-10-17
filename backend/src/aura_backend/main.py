from fastapi import FastAPI

from aura_backend.api.routes.feedback import router as feedback_router
from aura_backend.api.routes.items import router as items_router
from aura_backend.api.routes.preferences import router as preferences_router
from aura_backend.api.routes.health import router as health_router
from aura_backend.api.routes.profiles import router as profiles_router
from aura_backend.api.routes.suggestions import router as suggestions_router
from aura_backend.api.routes.wardrobe import router as wardrobe_router


def create_app() -> FastAPI:
    """Create the frontend-independent AURA API application."""
    app = FastAPI(
        title="AURA API",
        version="0.1.0",
        description="Backend API for AURA aesthetic matching.",
    )
    app.include_router(health_router)
    app.include_router(items_router)
    app.include_router(feedback_router)
    app.include_router(preferences_router)
    app.include_router(profiles_router)
    app.include_router(suggestions_router)
    app.include_router(wardrobe_router)
    return app


app = create_app()
