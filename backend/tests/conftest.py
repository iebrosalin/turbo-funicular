"""
Pytest configuration and shared fixtures.
"""
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import get_db
from app.db.base import Base
from app.models.asset import Asset
from app.models.group import Group
from app.models.scan import Scan


# Test database URL (SQLite in-memory for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async_session_maker = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session


@pytest.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing API endpoints."""
    
    # Override the dependency to use our test session
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()


# --- Mock Fixtures for Unit Tests ---

from unittest.mock import AsyncMock

@pytest.fixture
def async_session_mock():
    """Create a mock async session for unit testing services."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def test_asset_data():
    """Sample asset data for testing."""
    return {
        "ip_address": "192.168.1.10",
        "hostname": "test-host",
        "os_family": "Linux",
        "status": "active",
        "location": "Test DC"
    }


@pytest.fixture
def test_asset_instance(test_asset_data):
    """Create a sample Asset model instance."""
    asset = Asset(**test_asset_data)
    asset.id = 1
    return asset


@pytest.fixture
def test_group_data():
    """Sample group data for testing."""
    return {
        "name": "Test Group",
        "description": "A test group",
        "parent_id": None
    }


@pytest.fixture
def test_scan_data():
    """Sample scan data for testing."""
    return {
        "target": "192.168.1.0/24",
        "scan_type": "nmap",
        "options": "-sV",
        "status": "pending"
    }
