from fastapi import FastAPI

from aura_backend.api.routes.feedback import router as feedback_router
from aura_backend.api.routes.items import router as items_router
from aura_backend.api.routes.health import router as health_router


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
    return app


app = create_app()
