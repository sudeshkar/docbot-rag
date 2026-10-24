from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.container import get_rate_limiter
from app.core.config import get_settings
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.db.models import User
from app.db.session import get_db
from app.repositories.users import UserRepository
from app.routers.deps import client_ip
from app.schemas import Credentials, LoginRequest, TokenOut, UserOut
from app.services.rate_limit import RateLimiter

router = APIRouter(prefix="/auth", tags=["auth"])

# Verified against when the email doesn't exist, so a login takes the same time either way
# and response timing can't reveal which emails have accounts.
_DUMMY_HASH = hash_password("timing-equalizer")


@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(body: Credentials, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    if repo.get_by_email(body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    try:
        user = repo.add(body.email, hash_password(body.password))
        db.commit()
    except IntegrityError:  # concurrent signup with the same email
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    if not limiter.hit(f"login:{client_ip(request)}", get_settings().login_rate_limit_per_min, 60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts. Try again in a minute.")
    user = UserRepository(db).get_by_email(body.email)
    valid = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
