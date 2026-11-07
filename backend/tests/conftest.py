import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import Base, SessionLocal, engine, get_db  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    def override_get_db():
        session: Session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
