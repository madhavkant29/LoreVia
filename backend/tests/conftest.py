import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import get_db, Base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

TEST_DB = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://").replace("/postgres", "/test_lorevia")
engine_test = create_async_engine(TEST_DB, echo=False)
TestSession = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    async with TestSession() as s:
        yield s


@pytest.fixture
async def client(db):
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client):
    r = await client.post("/api/v1/auth/register", json={"email": "test@lorevia.app", "password": "testpass123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
