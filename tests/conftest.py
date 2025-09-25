import os
os.environ['DATABASE_URL'] = "sqlite:///./test.db"

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import after env
from app.main import app, get_db
from app.db import Base, SessionLocal as ProductionSessionLocal

SQLALCHEMY_DATABASE_URL_TEST = "sqlite:///./test.db"

engine_test = create_engine(
    SQLALCHEMY_DATABASE_URL_TEST, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

def override_startup():
    Base.metadata.create_all(bind=engine_test)

# Set overrides
app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
def client():
    override_startup()
    test_client = TestClient(app)
    yield test_client
    Base.metadata.drop_all(bind=engine_test)
    if os.path.exists("./test.db"):
        os.remove("./test.db")

# Override for direct DB access in tests
import app.db
app.db.SessionLocal = TestingSessionLocal

@pytest.fixture(autouse=True)
def mock_redis_and_stripe(monkeypatch):
    mock_r = Mock()
    mock_r.get.return_value = None
    mock_r.set.return_value = None
    monkeypatch.setattr('app.main.r', mock_r)
    
    mock_stripe = Mock()
    monkeypatch.setattr('app.main.stripe', mock_stripe)
