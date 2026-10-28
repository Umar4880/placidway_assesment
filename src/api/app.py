"""
FastAPI application factory and middleware configuration.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from src.utils.config import settings
from src.api.routes import chat, refresh, leads, gaps


class VercelRewriteMiddleware:
    """
    Middleware to ensure scope['path'] reflects the original request path
    when hosted behind Vercel serverless function rewrites.
    """
    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            current_path = scope.get("path", "")
            # If Vercel rewrote the path to the lambda entrypoint itself
            if current_path in ("/api/index.py", "/api/index", "/api/index/"):
                headers = dict(scope.get("headers", []))
                for h_key in (b"x-matched-path", b"x-forwarded-uri", b"x-original-url", b"x-vercel-rewrite-path"):
                    if h_key in headers:
                        val = headers[h_key].decode("utf-8").split("?")[0]
                        if val and not val.startswith("/api/index"):
                            scope["path"] = val
                            break
        await self.asgi_app(scope, receive, send)


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
    repo_root = Path(__file__).resolve().parent.parent.parent
    if (repo_root / "public").exists():
        static_dir = repo_root / "public"
    elif (repo_root / "static").exists():
        static_dir = repo_root / "static"
    elif getattr(settings, "STATIC_DIR", None) and Path(settings.STATIC_DIR).exists():
        static_dir = Path(settings.STATIC_DIR)
    else:
        static_dir = Path.cwd() / "public"
        if not static_dir.exists():
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

    # Mount static assets if directories exist
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

    # Asset extensions that should never be served index.html
    asset_extensions = (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".map")

    # Catch-all GET handler: safely serves static assets or SPA index.html
    @app.get("/{full_path:path}", response_class=FileResponse)
    def catch_all_get(full_path: str):
        clean_path = full_path.lstrip("/")
        if clean_path.startswith("static/"):
            clean_path = clean_path[len("static/"):]

        target = static_dir / clean_path
        if target.is_file():
            # Explicit media types for CSS and JS to ensure browsers parse correctly
            media_type = None
            if clean_path.endswith(".css"):
                media_type = "text/css"
            elif clean_path.endswith(".js"):
                media_type = "application/javascript"
            return FileResponse(str(target), media_type=media_type)

        # If it was an asset request and the file is missing, return 404 (DO NOT return index.html)
        if any(clean_path.endswith(ext) for ext in asset_extensions):
            return Response(content=f"Asset not found: {full_path}", status_code=404, media_type="text/plain")

        # For non-asset routes (SPA navigation), return index.html
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file), media_type="text/html")
        return HTMLResponse(
            f"<h1>PlacidWay Assistant: index.html not found</h1><p>Looked in: {static_dir}</p><p>Requested path: {full_path}</p>",
            status_code=404,
        )

    # Wrap app with Vercel rewrite middleware
    app.add_middleware(VercelRewriteMiddleware)

    return app


app = create_app()
