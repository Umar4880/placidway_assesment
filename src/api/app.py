"""
FastAPI application factory and middleware configuration.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
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

    # Serve index.html on root and common index paths
    @app.get("/", response_class=FileResponse)
    @app.get("/index.html", response_class=FileResponse)
    @app.get("/static/index.html", response_class=FileResponse)
    def serve_index():
        index_file = settings.STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file), media_type="text/html")
        return HTMLResponse("<h1>PlacidWay Assistant: UI index.html not found</h1>", status_code=404)

    # Mount static assets for CSS, JS, and static assets
    if settings.STATIC_DIR.exists():
        css_dir = settings.STATIC_DIR / "css"
        if css_dir.exists():
            app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
            app.mount("/static/css", StaticFiles(directory=str(css_dir)), name="static_css")

        js_dir = settings.STATIC_DIR / "js"
        if js_dir.exists():
            app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")
            app.mount("/static/js", StaticFiles(directory=str(js_dir)), name="static_js")

        app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

    return app


app = create_app()
