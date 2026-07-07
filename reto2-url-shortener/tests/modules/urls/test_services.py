"""Tests unitarios de la lógica de negocio de URLs (capa de services)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.exceptions import (
    AliasAlreadyExistsError,
    InvalidUrlError,
    ShortUrlExpiredError,
    ShortUrlNotFoundError,
)
from app.modules.urls.models import _utcnow


def test_create_generates_code(service):
    short_url, created = service.create_short_url("https://example.com")
    assert created is True
    assert short_url.code
    assert short_url.url == "https://example.com"
    assert short_url.is_custom is False
    assert short_url.expires_at is None


def test_idempotent_same_url_returns_same_code(service):
    first, created_1 = service.create_short_url("https://example.com/a")
    second, created_2 = service.create_short_url("https://example.com/a")

    assert created_1 is True
    assert created_2 is False  # reutilizado, no creado
    assert first.code == second.code


def test_different_urls_get_different_codes(service):
    a, _ = service.create_short_url("https://example.com/a")
    b, _ = service.create_short_url("https://example.com/b")
    assert a.code != b.code


def test_custom_alias_is_used_as_code(service):
    short_url, created = service.create_short_url(
        "https://example.com", alias="mylink"
    )
    assert created is True
    assert short_url.code == "mylink"
    assert short_url.is_custom is True


def test_duplicate_alias_raises_conflict(service):
    service.create_short_url("https://example.com/1", alias="dup")
    with pytest.raises(AliasAlreadyExistsError):
        service.create_short_url("https://example.com/2", alias="dup")


def test_alias_does_not_participate_in_url_dedup(service):
    """Una entrada con alias personalizado nunca se reutiliza en una petición posterior sin alias."""
    aliased, _ = service.create_short_url("https://example.com/x", alias="x1")
    generated, created = service.create_short_url("https://example.com/x")
    assert created is True
    assert generated.code != aliased.code
    assert generated.is_custom is False


@pytest.mark.parametrize(
    "bad_url",
    ["ftp://example.com", "not-a-url", "://missing-scheme", "http://"],
)
def test_invalid_url_raises(service, bad_url):
    with pytest.raises(InvalidUrlError):
        service.create_short_url(bad_url)


def test_redirect_increments_clicks(service):
    created, _ = service.create_short_url("https://example.com")
    assert created.clicks == 0

    service.get_for_redirect(created.code)
    service.get_for_redirect(created.code)

    stats = service.get_stats(created.code)
    assert stats.clicks == 2


def test_redirect_unknown_code_raises_not_found(service):
    with pytest.raises(ShortUrlNotFoundError):
        service.get_for_redirect("nope")


def test_stats_unknown_code_raises_not_found(service):
    with pytest.raises(ShortUrlNotFoundError):
        service.get_stats("nope")


def test_ttl_sets_expiry(service):
    short_url, _ = service.create_short_url("https://example.com", ttl=3600)
    assert short_url.expires_at is not None
    delta = short_url.expires_at - _utcnow()
    # Aproximadamente una hora por delante (con holgura por el tiempo de ejecución).
    assert timedelta(minutes=59) < delta <= timedelta(hours=1)


def test_expired_url_raises_gone_on_redirect(service, db_session):
    short_url, _ = service.create_short_url("https://example.com", ttl=3600)
    # Fuerza la expiración al pasado.
    short_url.expires_at = _utcnow() - timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(ShortUrlExpiredError):
        service.get_for_redirect(short_url.code)


def test_stats_still_available_after_expiry(service, db_session):
    short_url, _ = service.create_short_url("https://example.com", ttl=3600)
    short_url.expires_at = _utcnow() - timedelta(seconds=1)
    db_session.commit()

    # Las stats no dan 410 — todavía puedes inspeccionar un enlace expirado.
    stats = service.get_stats(short_url.code)
    assert stats.code == short_url.code


def test_expired_generated_url_is_not_reused(service, db_session):
    """Una entrada auto-generada expirada no debe satisfacer el dedup idempotente."""
    first, _ = service.create_short_url("https://example.com/reuse", ttl=3600)
    first.expires_at = _utcnow() - timedelta(seconds=1)
    db_session.commit()

    second, created = service.create_short_url("https://example.com/reuse")
    assert created is True
    assert second.code != first.code


def test_build_short_link(service):
    link = service.build_short_link("abc123")
    assert link.endswith("/abc123")
