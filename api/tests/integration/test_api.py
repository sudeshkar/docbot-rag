import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import container
from app.core.security import CSRF_HEADER, SESSION_COOKIE
from app.db.session import get_db
from app.ingest.url_safety import UnsafeUrl
from app.main import create_app
from app.rag.generation.answer import AnswerGenerator
from app.rag.generation.prompt import PromptBuilder
from app.services.chat import ChatService
from app.services.rate_limit import InMemoryRateLimiter
from tests.fakes import FakeLLM, FakeRetrieval, FakeStore, parse_sse

pytestmark = pytest.mark.integration


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue_ingest(self, document_id):
        self.jobs.append(("ingest", str(document_id)))

    async def enqueue_crawl(self, bot_id, url, max_pages):
        self.jobs.append(("crawl", str(bot_id), url, max_pages))


def strict_guard(url: str) -> None:
    if "127.0.0.1" in url or "localhost" in url:
        raise UnsafeUrl(url)


@pytest.fixture
def env(db, tmp_path, monkeypatch):
    app = create_app()
    queue, store, limiter = FakeQueue(), FakeStore(), InMemoryRateLimiter()
    monkeypatch.setattr(container.get_settings(), "storage_dir", tmp_path)
    app.dependency_overrides.update({
        get_db: lambda: db,
        container.get_job_queue: lambda: queue,
        container.get_vector_store: lambda: store,
        container.get_rate_limiter: lambda: limiter,
        container.get_url_guard: lambda: strict_guard,
        container.get_chat_service: lambda: ChatService(
            db, FakeRetrieval(), AnswerGenerator(FakeLLM(), PromptBuilder())
        ),
    })
    client = TestClient(app)
    return client, queue, store


def signup(client, email=None):
    email = email or f"{uuid4().hex}@example.com"
    r = client.post("/auth/signup", json={"email": email, "password": "correct-horse-1"})
    assert r.status_code == 201, r.text
    token = r.cookies[SESSION_COOKIE]
    # Tests juggle several users, so drop the shared cookie jar and authenticate explicitly.
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def create_bot(client, headers, name="Support"):
    r = client.post("/bots", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# --- auth -------------------------------------------------------------------------

def test_signup_login_me(env):
    client, _, _ = env
    client.post("/auth/signup", json={"email": "Dev@Example.com", "password": "correct-horse-1"})
    client.cookies.clear()
    r = client.post("/auth/login", json={"email": "dev@example.com", "password": "correct-horse-1"})
    assert r.status_code == 200 and r.json()["email"] == "dev@example.com"
    # the session cookie in the jar authenticates the next request
    assert client.get("/auth/me").json()["email"] == "dev@example.com"


def test_session_cookie_is_httponly_strict_and_token_never_in_body(env):
    client, _, _ = env
    r = client.post("/auth/signup", json={"email": "c@example.com", "password": "correct-horse-1"})
    assert "access_token" not in r.json()  # page scripts never see the token
    cookie = r.headers["set-cookie"].lower()
    assert f"{SESSION_COOKIE}=" in cookie
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/" in cookie


def test_cookie_auth_requires_csrf_header_on_state_changes(env):
    client, _, _ = env
    client.post("/auth/signup", json={"email": "csrf@example.com", "password": "correct-horse-1"})
    # a forged cross-site form post carries the cookie but can't add custom headers
    assert client.post("/bots", json={"name": "Forged"}).status_code == 403
    ok = client.post("/bots", json={"name": "Mine"}, headers={CSRF_HEADER: "1"})
    assert ok.status_code == 201
    # reads don't change state, so they don't need it
    assert client.get("/bots").status_code == 200


def test_bearer_auth_needs_no_csrf_header(env):
    client, _, _ = env
    h = signup(client)  # bearer only; browsers never attach this automatically
    assert client.post("/bots", json={"name": "API client"}, headers=h).status_code == 201


def test_logout_clears_the_session_cookie(env):
    client, _, _ = env
    client.post("/auth/signup", json={"email": "bye@example.com", "password": "correct-horse-1"})
    r = client.post("/auth/logout")
    assert r.status_code == 204
    assert f'{SESSION_COOKIE}=""' in r.headers["set-cookie"] or "max-age=0" in r.headers["set-cookie"].lower()
    assert client.get("/auth/me").status_code == 401


def test_duplicate_signup_and_bad_login(env):
    client, _, _ = env
    body = {"email": "dup@example.com", "password": "correct-horse-1"}
    assert client.post("/auth/signup", json=body).status_code == 201
    assert client.post("/auth/signup", json=body).status_code == 409
    bad = client.post("/auth/login", json={**body, "password": "wrong-password"})
    unknown = client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever-123"})
    # same status and message, so the endpoint can't be used to discover which emails exist
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json()


def test_login_is_rate_limited(env):
    client, _, _ = env
    body = {"email": "brute@example.com", "password": "wrong-password"}
    codes = [client.post("/auth/login", json=body).status_code for _ in range(12)]
    assert codes[-1] == 429


def test_protected_routes_need_a_valid_token(env):
    client, _, _ = env
    assert client.get("/bots").status_code == 401
    assert client.get("/bots", headers={"Authorization": "Bearer garbage"}).status_code == 401


# --- bots ------------------------------------------------------------------------

def test_bot_crud_and_ownership(env):
    client, _, store = env
    alice, mallory = signup(client), signup(client)
    bot = create_bot(client, alice)
    assert bot["public_key"].startswith("pk_") and bot["chunking_strategy"] == "markdown"

    listed = client.get("/bots", headers=alice).json()
    assert [b["id"] for b in listed] == [bot["id"]] and listed[0]["document_count"] == 0

    upd = client.patch(f"/bots/{bot['id']}", headers=alice,
                       json={"instructions": "Be brief.", "chunking_strategy": "semantic"})
    assert upd.json()["instructions"] == "Be brief." and upd.json()["chunking_strategy"] == "semantic"
    bad = client.patch(f"/bots/{bot['id']}", headers=alice, json={"chunking_strategy": "nope"})
    assert bad.status_code == 422

    # another user gets 404 (not 403) so bot ids can't be probed
    assert client.get(f"/bots/{bot['id']}", headers=mallory).status_code == 404
    assert client.delete(f"/bots/{bot['id']}", headers=mallory).status_code == 404

    old_key = bot["public_key"]
    rotated = client.post(f"/bots/{bot['id']}/rotate-key", headers=alice).json()
    assert rotated["public_key"] != old_key

    assert client.delete(f"/bots/{bot['id']}", headers=alice).status_code == 204
    assert store.dropped == [f"bot_{bot['id'].replace('-', '')}"]


def test_chunking_strategies_endpoint(env):
    client, _, _ = env
    names = {s["name"] for s in client.get("/meta/chunking-strategies").json()}
    assert names == {"fixed", "recursive", "markdown", "semantic"}


# --- documents -----------------------------------------------------------------------

def test_upload_validates_and_enqueues(env):
    client, queue, _ = env
    h = signup(client)
    bot = create_bot(client, h)
    url = f"/bots/{bot['id']}/documents/upload"

    ok = client.post(url, headers=h, files={"file": ("../../etc/faq.md", io.BytesIO(b"# FAQ\nhello"), "text/markdown")})
    assert ok.status_code == 202, ok.text
    doc = ok.json()
    assert doc["title"] == "faq.md" and doc["status"] == "queued"  # path stripped from the name
    assert queue.jobs == [("ingest", doc["id"])]

    exe = client.post(url, headers=h, files={"file": ("x.exe", io.BytesIO(b"MZ"), "application/octet-stream")})
    fake_pdf = client.post(url, headers=h, files={"file": ("x.pdf", io.BytesIO(b"<html>"), "application/pdf")})
    assert exe.status_code == fake_pdf.status_code == 400

    docs = client.get(f"/bots/{bot['id']}/documents", headers=h).json()
    assert [d["id"] for d in docs] == [doc["id"]]


def test_url_ingest_blocks_internal_addresses(env):
    client, queue, _ = env
    h = signup(client)
    bot = create_bot(client, h)
    r = client.post(f"/bots/{bot['id']}/documents/url", headers=h, json={"url": "http://127.0.0.1:5432/"})
    assert r.status_code == 400
    ok = client.post(f"/bots/{bot['id']}/documents/url", headers=h,
                     json={"url": "https://docs.example.com", "crawl": True, "max_pages": 5})
    assert ok.status_code == 202
    assert queue.jobs == [("crawl", bot["id"], "https://docs.example.com/", 5)]


def test_delete_document(env):
    client, _, store = env
    h = signup(client)
    bot = create_bot(client, h)
    doc = client.post(f"/bots/{bot['id']}/documents/upload", headers=h,
                      files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")}).json()
    assert client.delete(f"/bots/{bot['id']}/documents/{doc['id']}", headers=h).status_code == 204
    assert store.deleted and client.get(f"/bots/{bot['id']}/documents", headers=h).json() == []


# --- chat + analytics -------------------------------------------------------------------

def test_owner_playground_chat_streams_sse(env):
    client, _, _ = env
    h = signup(client)
    bot = create_bot(client, h)
    r = client.post(f"/bots/{bot['id']}/chat", headers=h, json={"question": "Refunds?"})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    assert events[-1][0] == "done" and events[-1][1]["answered"] is True

    stats = client.get(f"/bots/{bot['id']}/analytics?days=7", headers=h).json()
    assert stats["total_queries"] == 1 and len(stats["daily"]) == 7


# --- public widget ------------------------------------------------------------------------

def test_public_widget_flow(env):
    client, _, _ = env
    h = signup(client)
    bot = create_bot(client, h, name="Acme Help")
    key = bot["public_key"]

    info = client.get(f"/public/bots/{key}")
    assert info.json() == {"name": "Acme Help", "welcome_message": bot["welcome_message"], "allowed_origins": []}
    assert client.get("/public/bots/pk_nope").status_code == 404

    r = client.post(f"/public/bots/{key}/chat", json={"question": "Refunds?"},
                    headers={"X-Embed-Origin": "https://anywhere.com"})
    assert r.status_code == 200 and parse_sse(r.text)[-1][0] == "done"


def test_public_widget_enforces_allowed_origins(env):
    client, _, _ = env
    h = signup(client)
    bot = create_bot(client, h)
    client.patch(f"/bots/{bot['id']}", headers=h, json={"allowed_origins": ["https://acme.com/"]})
    url = f"/public/bots/{bot['public_key']}/chat"
    assert client.post(url, json={"question": "q"}, headers={"X-Embed-Origin": "https://evil.com"}).status_code == 403
    assert client.post(url, json={"question": "q"}).status_code == 403
    assert client.post(url, json={"question": "q"}, headers={"X-Embed-Origin": "https://acme.com"}).status_code == 200


def test_public_bot_exposes_allowed_origins_for_frame_ancestors(env):
    client, _, _ = env
    h = signup(client)
    bot = create_bot(client, h)
    client.patch(f"/bots/{bot['id']}", headers=h, json={"allowed_origins": ["https://acme.com/"]})
    info = client.get(f"/public/bots/{bot['public_key']}").json()
    assert info["allowed_origins"] == ["https://acme.com"]
    assert set(info) == {"name", "welcome_message", "allowed_origins"}  # nothing private leaks


def test_public_widget_is_rate_limited(env):
    client, _, _ = env
    h = signup(client)
    bot = create_bot(client, h)
    url = f"/public/bots/{bot['public_key']}/chat"
    codes = [client.post(url, json={"question": "q"}).status_code for _ in range(25)]
    assert codes.count(429) > 0


# --- hardening -----------------------------------------------------------------------------

def test_security_headers_and_health(env):
    client, _, _ = env
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "referrer-policy" in r.headers


def test_oversized_question_rejected(env):
    client, _, _ = env
    h = signup(client)
    bot = create_bot(client, h)
    r = client.post(f"/bots/{bot['id']}/chat", headers=h, json={"question": "x" * 5000})
    assert r.status_code == 422


# --- input validation over HTTP ----------------------------------------------------------

def test_script_payloads_in_bot_fields_are_rejected_and_nothing_is_stored(env):
    client, _, _ = env
    h = signup(client)
    r = client.post("/bots", json={"name": "<script>alert(document.cookie)</script>"}, headers=h)
    assert r.status_code in (400, 422)
    bot = create_bot(client, h)
    r = client.patch(f"/bots/{bot['id']}", json={"welcome_message": "<img src=x onerror=alert(1)>"}, headers=h)
    assert r.status_code in (400, 422)
    assert [b["name"] for b in client.get("/bots", headers=h).json()] == ["Support"]
    assert client.get(f"/bots/{bot['id']}", headers=h).json()["welcome_message"] != "<img src=x onerror=alert(1)>"
