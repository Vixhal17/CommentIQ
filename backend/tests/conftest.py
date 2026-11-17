import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.db.models import Base
from backend.app.llm.mock_provider import MockProvider
from backend.app.llm.client import LLMClient

@pytest.fixture(scope="session")
def engine():
    # Use in-memory SQLite with StaticPool for fast, zero-lock testing on Windows
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()

@pytest.fixture(scope="function")
def db_session(engine):
    # Reset all tables before each test function to guarantee complete test isolation
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())

    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture(scope="function")
def mock_llm():
    provider = MockProvider()
    return provider

@pytest.fixture(scope="function")
def llm_client(db_session, mock_llm):
    client = LLMClient(db=db_session, mock_provider=mock_llm)
    return client
