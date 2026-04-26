import sys
import os

# Add the project root directory to path so 'backend' package can be found
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator, Generator
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.db.session import get_db
from backend.db.base import Base
from backend.models.asset import Asset
from backend.models.group import Group
from backend.models.scan import Scan


# Test database URL (SQLite in-memory for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def test_engine():
    """Create a test database engine for each test function."""
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


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test with rollback."""
    async_session_maker = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing API endpoints."""
    
    # Override the dependency to use our test session directly
    # We need to provide a synchronous generator that yields the session
    def override_get_db():
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


# --- Fixtures for Integration Tests ---

@pytest_asyncio.fixture
async def test_asset(db_session: AsyncSession):
    """Create a test asset in the database and return it."""
    asset = Asset(
        ip_address="192.168.1.50",
        hostname="integration-test-host",
        os_family="Linux",
        status="active"
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)
    return asset


@pytest_asyncio.fixture
async def test_group(db_session: AsyncSession):
    """Create a test group in the database and return it."""
    group = Group(
        name="Integration Test Group",
        description="Group for integration tests"
    )
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)
    return group


@pytest_asyncio.fixture
async def test_group_hierarchy(db_session: AsyncSession):
    """Create a hierarchy of groups: Parent -> Child."""
    parent = Group(name="Parent Group", description="Parent")
    child = Group(name="Child Group", description="Child", parent_id=None)  # Will set parent_id after parent is saved
    
    db_session.add(parent)
    await db_session.commit()
    await db_session.refresh(parent)
    
    child.parent_id = parent.id
    db_session.add(child)
    await db_session.commit()
    await db_session.refresh(child)
    
    return {"parent": parent, "child": child}


@pytest_asyncio.fixture
async def test_scan(db_session: AsyncSession):
    """Create a test scan in the database and return it."""
    from backend.models.scan import Scan
    scan = Scan(
        name="Integration Test Scan",
        target="192.168.1.0/24",
        scan_type="nmap",
        status="pending"
    )
    db_session.add(scan)
    await db_session.commit()
    await db_session.refresh(scan)
    return scan


@pytest_asyncio.fixture
async def asset_in_group(db_session: AsyncSession):
    """Create an asset assigned to a group."""
    group = Group(name="Asset Test Group", description="Group with assets")
    db_session.add(group)
    await db_session.flush()  # Get group ID without committing
    
    asset = Asset(
        ip_address="192.168.1.100",
        hostname="asset-in-group",
        os_family="Linux",
        status="active"
    )
    db_session.add(asset)
    await db_session.flush()  # Get asset ID without committing
    
    # Associate asset with group using many-to-many relationship via the association table
    from backend.models.asset import asset_groups
    stmt = asset_groups.insert().values(asset_id=asset.id, group_id=group.id)
    await db_session.execute(stmt)
    await db_session.commit()
    
    # Load the groups relationship explicitly before returning
    await db_session.refresh(asset, attribute_names=['groups'])
    
    return asset
