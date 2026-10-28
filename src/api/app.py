"""
FastAPI application factory and middleware configuration.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.utils.config import settings
from src.api.routes import chat, refresh, leads, gaps


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="PlacidWay Grounded Medical Tourism Knowledge Assistant",
        description="Grounded AI Assistant with zero hallucination and hybrid retrieval.",
        version="1.0.0",
    )

    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API Routers
    app.include_router(chat.router)
    app.include_router(refresh.router)
    app.include_router(leads.router)
    app.include_router(gaps.router)

    @app.get("/api/health")
    def health_check():
        return {
            "status": "healthy",
            "service": "PlacidWay Grounded Medical Knowledge Assistant",
            "version": "1.0.0",
        }

    # Mount static files for the chat web UI
    if settings.STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(settings.STATIC_DIR), html=True), name="static")

    return app


app = create_app()
