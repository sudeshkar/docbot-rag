import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import hash_password, verify_password
from app.schemas import Credentials

STRONG_SECRET = "x" * 48


# --- passwords (bcrypt only uses the first 72 bytes and bcrypt 5 rejects longer input) ----

def test_signup_rejects_password_over_72_utf8_bytes():
    with pytest.raises(ValidationError, match="72 bytes"):
        Credentials(email="a@example.com", password="é" * 40)  # 40 chars, 80 bytes


def test_signup_accepts_password_of_exactly_72_bytes():
    assert Credentials(email="a@example.com", password="a" * 72).password == "a" * 72


def test_verify_password_returns_false_for_overlong_input_instead_of_raising():
    assert verify_password("a" * 100, hash_password("a" * 72)) is False


def test_password_round_trip():
    hashed = hash_password("correct horse battery")
    assert hashed != "correct horse battery" and hashed.startswith("$2")
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong", hashed)


# --- JWT secret: a weak or default secret lets anyone forge login tokens ------------------

@pytest.fixture(autouse=True)
def no_ambient_settings(monkeypatch):
    # The developer's shell may export these; tests must see only what they pass in.
    for name in ("JWT_SECRET", "APP_ENV"):
        monkeypatch.delenv(name, raising=False)

def test_production_refuses_default_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, app_env="production")


def test_production_refuses_short_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, app_env="production", jwt_secret="too-short")


def test_production_accepts_strong_jwt_secret():
    assert Settings(_env_file=None, app_env="production", jwt_secret=STRONG_SECRET).jwt_secret == STRONG_SECRET


def test_development_allows_default_secret():
    assert Settings(_env_file=None, app_env="development").app_env == "development"


# --- session cookie flags ---------------------------------------------------------------------

def test_session_cookie_is_secure_in_production():
    from app.core.security import session_cookie_params

    params = session_cookie_params(Settings(_env_file=None, app_env="production", jwt_secret=STRONG_SECRET))
    assert params["secure"] is True and params["httponly"] is True and params["samesite"] == "strict"
    assert params["max_age"] == 60 * 24 * 7 * 60


def test_session_cookie_allows_plain_http_in_development():
    from app.core.security import session_cookie_params

    # localhost dev runs over http; a Secure cookie would never be sent back
    assert session_cookie_params(Settings(_env_file=None, app_env="development"))["secure"] is False
