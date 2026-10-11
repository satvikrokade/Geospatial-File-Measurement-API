from __future__ import annotations
import asyncio
import pathlib
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import Settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
import os
TEST_DB_URL = os.getenv('TEST_DATABASE_URL', 'sqlite+aiosqlite:///./test.db')
FIXTURE_DIR = pathlib.Path(__file__).parent / 'fixtures'

@pytest.fixture(scope='session')
def event_loop() -> Generator:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope='session')
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, autocommit=False, autoflush=False, expire_on_commit=False)
    async with TestSession() as session:
        yield session
        await session.rollback()

@pytest_asyncio.fixture
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:

    async def override_get_db():
        yield test_db
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture
def geojson_file() -> pathlib.Path:
    return FIXTURE_DIR / 'geojson' / 'test_polygons.geojson'

@pytest.fixture
def simple_geojson_file() -> pathlib.Path:
    return FIXTURE_DIR / 'geojson' / 'simple.geojson'

@pytest.fixture
def kml_file() -> pathlib.Path:
    return FIXTURE_DIR / 'kml' / 'test_polygons.kml'

@pytest.fixture
def shapefile_zip() -> pathlib.Path:
    path = FIXTURE_DIR / 'shapefiles' / 'test_london.zip'
    if not path.exists():
        import subprocess, sys
        subprocess.run([sys.executable, 'scripts/create_shapefile_fixture.py'], check=True)
    return path
