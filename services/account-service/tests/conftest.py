"""Test configuration for account-service integration tests."""

import os

os.environ["TESTING"] = "1"
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("USER_SERVICE_URL", "http://mock-user-service:8001")

import pytest
from app.database import Base, get_db
from app.models import account, account_groups, outbox  # noqa: F401
from app.models.common import account_group_user_association  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, event
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def _make_auth_header(user_id: int = 1) -> dict[str, str]:
    """Create a valid JWT Authorization header for testing."""
    from app.auth import create_access_token

    token = create_access_token(user_id=user_id, username="testuser", email="test@example.com")
    return {"Authorization": f"Bearer {token}"}
