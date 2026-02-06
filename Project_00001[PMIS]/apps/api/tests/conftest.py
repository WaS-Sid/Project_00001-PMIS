import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.tools.models import Base
from app.tools.user_context import UserContext, Role


@pytest.fixture(scope="function")
def db_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a fresh database session for each test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def admin_user():
    """Admin user context for testing."""
    return UserContext(
        user_id="admin_001",
        name="Admin User",
        roles=[Role.ADMIN, Role.ANALYST],
    )


@pytest.fixture
def analyst_user():
    """Analyst user context for testing."""
    return UserContext(
        user_id="analyst_001",
        name="Analyst User",
        roles=[Role.ANALYST],
    )


@pytest.fixture
def operator_user():
    """Operator user context for testing."""
    return UserContext(
        user_id="operator_001",
        name="Operator User",
        roles=[Role.OPERATOR],
    )


@pytest.fixture
def viewer_user():
    """Viewer user context for testing (read-only)."""
    return UserContext(
        user_id="viewer_001",
        name="Viewer User",
        roles=[Role.VIEWER],
    )
