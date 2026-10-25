"""Pytest configuration and async test fixtures for PayGuard AI."""

import os
import shutil
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set testing environment variables before importing app
_test_upload_dir = tempfile.mkdtemp(prefix="payguard_test_uploads_")
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_super_secret_key_for_unit_tests_32chars"
os.environ["MASK_PII_ENABLED"] = "true"
os.environ["EMBEDDING_PROVIDER"] = "openai"
os.environ["OPENAI_API_KEY"] = ""
os.environ["UPLOAD_STORAGE_DIR"] = _test_upload_dir

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models.base import Base

# In-memory SQLite async test engine
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    future=True,
)

from sqlalchemy import event


@event.listens_for(test_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Session setup: ensures upload storage is isolated to a temporary directory."""
    settings.UPLOAD_STORAGE_DIR = _test_upload_dir
    yield
    shutil.rmtree(_test_upload_dir, ignore_errors=True)


@pytest.fixture
async def db_session():
    """Provides a fresh database session for each test with all tables created."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(db_session: AsyncSession):
    """Provides an AsyncClient bound to the FastAPI app with the test DB session override."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()
