import logging
import secrets
from starlette.middleware.sessions import SessionMiddleware
from app.config import settings
from app.auth import router as auth_router
from app.brands import router as brands_router
from app.campaigns import router as campaigns_router
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.db import engine

app = FastAPI(title="AI Marketing Manager", version="0.1.0")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret or secrets.token_urlsafe(48),
                   session_cookie="amm_oauth", max_age=600, same_site="lax", https_only=settings.cookie_secure)
app.include_router(auth_router)
app.include_router(brands_router)
app.include_router(campaigns_router)

@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

logger = logging.getLogger(__name__)

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "backend"}

@app.get("/api/health/ready")
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connection.execute(text("SELECT id, owner_id FROM brands LIMIT 1"))
            connection.execute(text("SELECT token_hash FROM login_sessions LIMIT 1"))
            connection.execute(text("SELECT id FROM content_revisions LIMIT 1"))
        return {"status": "ok", "database": "connected", "schema": "ready"}
    except SQLAlchemyError:
        logger.warning("Database readiness check failed")
        return JSONResponse(status_code=503, content={
            "status": "unavailable", "database": "not_ready"})
