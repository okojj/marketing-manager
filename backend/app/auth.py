import hashlib
import secrets
from datetime import datetime, timedelta
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.base_client.errors import OAuthError
from joserfc.errors import JoseError
from httpx import HTTPError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.db import get_db
from app.models import LoginSession, User

router = APIRouter(prefix="/api/auth", tags=["auth"])
COOKIE = "amm_session"
oauth = OAuth()
oauth.register(name="google", client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256", "timeout": 15})

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def require_origin(request: Request):
    # Require the exact configured origin for every cookie-authenticated mutation.
    if request.headers.get("origin") != settings.app_origin:
        raise HTTPException(403, "허용되지 않은 요청 출처입니다.")

def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    session = db.get(LoginSession, token_hash(token)) if token else None
    if not session or session.expires_at <= datetime.utcnow():
        raise HTTPException(401, "로그인이 필요합니다.")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "로그인이 필요합니다.")
    return user

@router.get("/config")
def config():
    return {"google_enabled": settings.google_ready}

@router.get("/google/login")
async def login(request: Request):
    if not settings.google_ready:
        return RedirectResponse(settings.app_origin + "/?auth_error=not_configured", status_code=303)
    request.session.clear()
    return await oauth.google.authorize_redirect(request,
        settings.app_origin + "/api/auth/google/callback", prompt="select_account")

@router.get("/google/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    if not settings.google_ready:
        return RedirectResponse(settings.app_origin + "/?auth_error=not_configured", status_code=303)
    try:
        # Authlib validates OAuth state and the ID token signature, issuer, audience,
        # expiration and nonce against Google's discovery metadata and signing keys.
        token = await oauth.google.authorize_access_token(request)
        info = token.get("userinfo")
        if not info or not info.get("sub") or info.get("email_verified") is not True or not info.get("email"):
            raise ValueError("Unverified identity")
    except (OAuthError, JoseError, HTTPError, ValueError, KeyError):
        request.session.clear()
        return RedirectResponse(settings.app_origin + "/?auth_error=login_failed", status_code=303)
    request.session.clear()
    user = db.scalar(select(User).where(User.google_sub == info["sub"]))
    if not user:
        user = User(google_sub=info["sub"], email=info["email"], name=info.get("name", info["email"])[:200])
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            user = db.scalar(select(User).where(User.google_sub == info["sub"]))
            if user is None:
                raise
    user.email = info["email"]
    user.name = info.get("name", info["email"])[:200]
    old = request.cookies.get(COOKIE)
    if old:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(old)))
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= datetime.utcnow()))
    raw = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=token_hash(raw), user_id=user.id,
                        expires_at=datetime.utcnow() + timedelta(days=settings.session_days)))
    db.commit()
    response = RedirectResponse(settings.app_origin + "/", status_code=303)
    response.set_cookie(COOKIE, raw, httponly=True, secure=settings.cookie_secure,
                        samesite="lax", max_age=settings.session_days * 86400, path="/")
    return response

@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email}

@router.post("/logout", dependencies=[Depends(require_origin)], status_code=204)
def logout(request: Request, db: Session = Depends(get_db)):
    raw = request.cookies.get(COOKIE)
    if raw:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(raw)))
        db.commit()
    request.session.clear()
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")
    return response
