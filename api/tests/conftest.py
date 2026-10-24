import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://docbot:docbot@localhost:5433/docbot_test"
)
os.environ.setdefault("CHROMA_HOST", "localhost")
os.environ.setdefault("CHROMA_PORT", "8001")


def _ensure_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": target.database})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine():
    from app.db.models import Base

    try:
        _ensure_database(TEST_DATABASE_URL)
    except Exception as exc:  # pragma: no cover - only when docker isn't running
        pytest.skip(f"Postgres not available: {exc}")
    eng = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    """Each test runs inside a transaction that is rolled back: fast and fully isolated."""
    conn = engine.connect()
    trans = conn.begin()
    session = sessionmaker(bind=conn, join_transaction_mode="create_savepoint")()
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def chroma_namespace():
    """A throwaway Chroma collection name, dropped after the test."""
    from app.rag.vectorstores.chroma import ChromaVectorStore

    store = ChromaVectorStore(os.environ["CHROMA_HOST"], int(os.environ["CHROMA_PORT"]))
    if not store.ping():
        pytest.skip("Chroma not available")
    name = f"test_{uuid.uuid4().hex}"
    yield store, name
    store.drop_namespace(name)
