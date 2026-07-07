"""Fixtures de pytest compartidas.

Cada test recibe una base SQLite in-memory aislada (StaticPool para que el
esquema se comparta entre conexiones dentro del test). El rate limiter se
sobrescribe con un cubo muy permisivo por defecto; el test dedicado al 429
instala uno estricto.
"""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.rate_limiter import RateLimiter, rate_limiter
from app.database import Base
from app.main import app
from app.modules.urls.dependencies import get_db
from app.modules.urls.services import UrlService

# Importa el modelo para que su tabla se registre en Base.metadata.
from app.modules.urls import models  # noqa: F401
from shared.token_bucket import TokenBucketLimiter


@pytest.fixture
def engine():
    """Un engine SQLite in-memory nuevo con el esquema creado."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(bind=eng)
        eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture
def db_session(session_factory) -> Iterator[Session]:
    """Una sesión de DB para testear los services directamente."""
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def service(db_session) -> UrlService:
    return UrlService(db_session)


def _permissive_rate_limiter() -> RateLimiter:
    # Cubo enorme: no salta nunca durante los tests normales.
    return RateLimiter(TokenBucketLimiter(capacity=10_000, refill_per_sec=10_000))


@pytest.fixture
def client(session_factory) -> Iterator[TestClient]:
    """Un TestClient conectado a la DB de test con un rate limiter permisivo."""

    def _override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[rate_limiter] = _permissive_rate_limiter()
    # Se instancia sin el context manager `with` para que el lifespan de la app
    # (que tocaría la DB real en archivo vía init_db) no se ejecute — el esquema
    # de test lo crea el fixture `engine` y se alcanza mediante el override de
    # get_db.
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
