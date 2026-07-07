"""Tests de integración vía TestClient sobre las rutas HTTP."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limiter import RateLimiter, rate_limiter
from app.main import app
from app.modules.urls.dependencies import get_db
from shared.token_bucket import TokenBucketLimiter


# -- Nivel base ----------------------------------------------------------


def test_shorten_returns_201_with_code_and_short(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"]
    assert body["short"].endswith("/" + body["code"])


def test_redirect_returns_302_with_location(client):
    code = client.post(
        "/shorten", json={"url": "https://example.com/dest"}
    ).json()["code"]

    resp = client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com/dest"


def test_redirect_unknown_code_returns_404(client):
    resp = client.get("/doesnotexist", follow_redirects=False)
    assert resp.status_code == 404


@pytest.mark.parametrize("bad_url", ["ftp://example.com", "not-a-url", "hello"])
def test_invalid_url_returns_400(client, bad_url):
    resp = client.post("/shorten", json={"url": bad_url})
    assert resp.status_code == 400


def test_missing_url_returns_400(client):
    resp = client.post("/shorten", json={})
    assert resp.status_code == 400


# -- Nivel medio ---------------------------------------------------------


def test_idempotency_same_url_same_code(client):
    first = client.post("/shorten", json={"url": "https://example.com/idem"})
    second = client.post("/shorten", json={"url": "https://example.com/idem"})

    assert first.status_code == 201     # creado
    assert second.status_code == 200    # reutilizado
    assert first.json()["code"] == second.json()["code"]


def test_custom_alias(client):
    resp = client.post(
        "/shorten", json={"url": "https://example.com", "alias": "promo"}
    )
    assert resp.status_code == 201
    assert resp.json()["code"] == "promo"

    redirect = client.get("/promo", follow_redirects=False)
    assert redirect.status_code == 302


def test_duplicate_alias_returns_409(client):
    client.post("/shorten", json={"url": "https://a.com", "alias": "taken"})
    resp = client.post("/shorten", json={"url": "https://b.com", "alias": "taken"})
    assert resp.status_code == 409


def test_stats_reports_clicks_and_metadata(client):
    code = client.post(
        "/shorten", json={"url": "https://example.com/stats"}
    ).json()["code"]

    client.get(f"/{code}", follow_redirects=False)
    client.get(f"/{code}", follow_redirects=False)

    resp = client.get(f"/stats/{code}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["clicks"] == 2
    assert body["url"] == "https://example.com/stats"
    assert body["code"] == code
    assert "created_at" in body


def test_stats_unknown_code_returns_404(client):
    resp = client.get("/stats/nope")
    assert resp.status_code == 404


# -- Nivel avanzado ------------------------------------------------------


def test_ttl_expired_returns_410(client):
    # ttl=1s, luego esperamos a que pase.
    code = client.post(
        "/shorten", json={"url": "https://example.com/ttl", "ttl": 1}
    ).json()["code"]

    import time

    time.sleep(1.1)
    resp = client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 410


def test_rate_limit_returns_429_when_exceeded():
    """Un limiter por IP estricto devuelve 429 una vez drenado el cubo.

    Este test NO usa el fixture permisivo `client`; instala un cubo diminuto
    (capacity=2, sin refill) para que la tercera petición dispare el límite.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    from app.modules.urls import models  # noqa: F401  (registra la tabla)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def _override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    strict = RateLimiter(TokenBucketLimiter(capacity=2, refill_per_sec=0))
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[rate_limiter] = strict
    try:
        c = TestClient(app)
        assert c.post("/shorten", json={"url": "https://e.com/1"}).status_code == 201
        assert c.post("/shorten", json={"url": "https://e.com/2"}).status_code == 201
        # Cubo drenado -> 429.
        assert c.post("/shorten", json={"url": "https://e.com/3"}).status_code == 429
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_routes_have_no_api_v1_prefix(client):
    """Pese al agrupador versionado, las rutas públicas no llevan prefijo /api/v1."""
    assert client.post(
        "/shorten", json={"url": "https://example.com"}
    ).status_code == 201
    # La ruta con prefijo NO debe existir.
    assert client.post(
        "/api/v1/shorten", json={"url": "https://example.com"}
    ).status_code == 404
