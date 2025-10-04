from __future__ import annotations

from collections.abc import Generator

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure required settings exist before importing application modules
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "testing-secret")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_DB", "northstar_test")
os.environ.setdefault("POSTGRES_USER", "tester")
os.environ.setdefault("POSTGRES_PASSWORD", "tester")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("QUEUE_MODE", "direct")
os.environ.setdefault("ROUTER_MODE", "static")
os.environ.setdefault("LLM_PROVIDER", "cerebras")

import app.deps as deps
from app.main import create_app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    deps.engine = engine
    deps.SessionLocal = TestingSessionLocal

    app = create_app()

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    with deps.SessionLocal() as session:
        yield session
