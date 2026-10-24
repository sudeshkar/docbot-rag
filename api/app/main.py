from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.container import get_vector_store
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.routers import auth, bots, documents, public

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]


class SecurityHeadersMiddleware:
    """Pure ASGI middleware (unlike BaseHTTPMiddleware it never buffers streamed responses)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"].extend(SECURITY_HEADERS)
            await send(message)

        await self.app(scope, receive, send_with_headers)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="DocBot API", version="1.0.0")
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,  # bearer tokens, not cookies: no CSRF surface
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Embed-Origin"],
    )
    for r in (auth.router, bots.router, documents.router, public.router):
        app.include_router(r)

    @app.get("/health")
    def health():
        db_ok = True
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
        except Exception:
            db_ok = False
        return {"status": "ok" if db_ok else "degraded", "database": db_ok,
                "vector_store": get_vector_store().ping()}

    return app


app = create_app()
