import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db

_bearer = HTTPBearer(auto_error=False)

# The browser session lives in an httpOnly cookie, so page scripts (and any XSS) can never read it.
SESSION_COOKIE = "docbot_session"
# Cookie-authenticated state changes must carry this header. A cross-site form or <img> can make the
# browser send the cookie, but it can't add a custom header (and CORS blocks scripted cross-origin ones).
CSRF_HEADER = "X-DocBot-CSRF"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# bcrypt only uses the first 72 bytes of a password, and bcrypt 5 raises on longer input.
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    encoded = password.encode()
    if len(encoded) > BCRYPT_MAX_BYTES:
        return False  # can't match any stored hash (signup rejects these); never a 500
    return bcrypt.checkpw(encoded, hashed.encode())


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> UUID:
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    return UUID(payload["sub"])


def session_cookie_params(settings: Settings) -> dict:
    return {
        "key": SESSION_COOKIE,
        "httponly": True,
        # Never sent on cross-site requests, not even top-level links: the dashboard has no inbound deep links that need it.
        "samesite": "strict",
        # Dev runs on plain-http localhost, where a Secure cookie would be dropped.
        "secure": settings.app_env == "production",
        "max_age": settings.jwt_expire_minutes * 60,
        "path": "/",
    }


def new_public_key() -> str:
    return "pk_" + secrets.token_urlsafe(24)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    # Bearer for API clients; the cookie for the browser dashboard.
    if creds is not None:
        token = creds.credentials
    else:
        token = request.cookies.get(SESSION_COOKIE)
        if token is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
        if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing CSRF header")
    try:
        user_id = decode_access_token(token)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user
