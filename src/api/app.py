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

    # Determine static directory with reliable fallbacks
    # src/api/app.py -> parent (api) -> parent (src) -> parent (project root)
    repo_root = Path(__file__).resolve().parent.parent.parent
    static_candidate = repo_root / "static"
    if static_candidate.exists():
        static_dir = static_candidate
    elif getattr(settings, "STATIC_DIR", None) and Path(settings.STATIC_DIR).exists():
        static_dir = Path(settings.STATIC_DIR)
    else:
        # Fallback to local 'static' in runtime current working dir
        static_dir = Path.cwd() / "static"

    # Serve index.html on root and Vercel entrypoint paths
    @app.get("/", response_class=FileResponse)
    @app.get("/index.html", response_class=FileResponse)
    @app.get("/api/index.py", response_class=FileResponse)
    @app.get("/api/index", response_class=FileResponse)
    @app.get("/static/index.html", response_class=FileResponse)
    def serve_index():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file), media_type="text/html")
        return HTMLResponse(
            f"<h1>PlacidWay Assistant: index.html not found</h1><p>Looked in: {static_dir}</p>",
            status_code=404,
        )

    # Mount static assets
    if static_dir.exists():
        css_dir = static_dir / "css"
        if css_dir.exists():
            app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
            app.mount("/static/css", StaticFiles(directory=str(css_dir)), name="static_css")

        js_dir = static_dir / "js"
        if js_dir.exists():
            app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")
            app.mount("/static/js", StaticFiles(directory=str(js_dir)), name="static_js")

        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Catch-all GET handler: guarantees static assets or SPA index.html is always returned
    @app.get("/{full_path:path}", response_class=FileResponse)
    def catch_all_get(full_path: str):
        # 1. Check if it's a static file request
        clean_path = full_path.lstrip("/")
        if clean_path.startswith("static/"):
            clean_path = clean_path[len("static/"):]
        target = static_dir / clean_path
        if target.is_file():
            return FileResponse(str(target))

        # 2. Otherwise serve index.html for SPA routing
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file), media_type="text/html")
        return HTMLResponse(
            f"<h1>PlacidWay Assistant: index.html not found</h1><p>Looked in: {static_dir}</p><p>Requested path: {full_path}</p>",
            status_code=404,
        )

    return app


app = create_app()
