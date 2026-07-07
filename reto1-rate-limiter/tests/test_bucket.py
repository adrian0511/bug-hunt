"""Tests unitarios del TokenBucketLimiter compartido usado por el Reto 1."""

from __future__ import annotations

import pytest

from shared.token_bucket import TokenBucketLimiter


def test_example_case_exact():
    """El ejemplo exacto del enunciado del reto.

    capacity=2, refillPerSec=1:
        0 a -> ALLOW    (2 -> 1)
        0 a -> ALLOW    (1 -> 0)
        0 a -> DENY     (0)
        500 a -> DENY   (+0.5 -> 0.5, < 1)
        1000 a -> ALLOW (+0.5 -> 1.0 -> 0)
    """
    limiter = TokenBucketLimiter(capacity=2, refill_per_sec=1)
    requests = [(0, "a"), (0, "a"), (0, "a"), (500, "a"), (1000, "a")]
    results = [limiter.allow(key, ts) for ts, key in requests]
    assert results == [True, True, False, False, True]


def test_keys_are_independent():
    """Cada key tiene su propio cubo; drenar uno no afecta a otro."""
    limiter = TokenBucketLimiter(capacity=1, refill_per_sec=0)

    assert limiter.allow("a", 0) is True   # a: 1 -> 0
    assert limiter.allow("a", 0) is False  # a: vacío
    assert limiter.allow("b", 0) is True   # b empieza lleno, independiente
    assert limiter.allow("b", 0) is False


def test_refill_never_exceeds_capacity():
    """Un periodo largo de inactividad rellena hasta capacity pero nunca por encima."""
    limiter = TokenBucketLimiter(capacity=2, refill_per_sec=1000)

    assert limiter.allow("a", 0) is True   # 2 -> 1
    assert limiter.allow("a", 0) is True   # 1 -> 0
    # Un tiempo transcurrido enorme rellenaría miles de tokens, pero se acota a 2.
    assert limiter.allow("a", 10_000) is True   # acotado 2 -> 1
    assert limiter.allow("a", 10_000) is True   # 1 -> 0
    assert limiter.allow("a", 10_000) is False  # 0, no hay más en este instante


def test_refill_per_sec_zero_never_recovers():
    """Con refillPerSec=0 una key drenada se deniega para siempre."""
    limiter = TokenBucketLimiter(capacity=1, refill_per_sec=0)

    assert limiter.allow("a", 0) is True
    assert limiter.allow("a", 0) is False
    assert limiter.allow("a", 1_000_000) is False  # pasa el tiempo, sigue vacío


def test_fractional_refill_accumulates():
    """Los refills fraccionarios se acumulan entre peticiones denegadas hasta >= 1 token."""
    limiter = TokenBucketLimiter(capacity=1, refill_per_sec=1)

    assert limiter.allow("a", 0) is True    # 1 -> 0
    assert limiter.allow("a", 300) is False  # +0.3 -> 0.3
    assert limiter.allow("a", 600) is False  # +0.3 -> 0.6
    assert limiter.allow("a", 900) is False  # +0.3 -> 0.9
    assert limiter.allow("a", 1000) is True  # +0.1 -> 1.0 -> 0


def test_full_bucket_allows_capacity_requests_at_once():
    """Una key nueva permite exactamente `capacity` peticiones en el mismo instante."""
    limiter = TokenBucketLimiter(capacity=3, refill_per_sec=1)
    results = [limiter.allow("a", 0) for _ in range(4)]
    assert results == [True, True, True, False]


def test_non_increasing_timestamp_does_not_add_tokens():
    """Un timestamp que retrocede no debe conceder un relleno negativo/extra."""
    limiter = TokenBucketLimiter(capacity=2, refill_per_sec=1)

    assert limiter.allow("a", 1000) is True   # 2 -> 1
    assert limiter.allow("a", 1000) is True   # 1 -> 0
    # Timestamp anterior: sin relleno negativo, sigue vacío.
    assert limiter.allow("a", 500) is False


@pytest.mark.parametrize("capacity", [0, -1, -0.5])
def test_invalid_capacity_raises(capacity):
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=capacity, refill_per_sec=1)


@pytest.mark.parametrize("refill", [-1, -0.001])
def test_invalid_refill_raises(refill):
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=1, refill_per_sec=refill)
