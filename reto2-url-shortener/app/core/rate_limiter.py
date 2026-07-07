"""Rate limiting por IP como dependency de FastAPI.

Envuelve el ``TokenBucketLimiter`` compartido (de ``shared/token_bucket``) —el
mismísimo algoritmo usado por el Reto 1— indexado por la IP del cliente. Cuando
un cliente supera su presupuesto, la dependency lanza ``HTTPException(429)``.

El rate limiter es una preocupación de la capa HTTP, así que lanzar
``HTTPException`` aquí es apropiado (a diferencia de los services, que lanzan
excepciones de dominio).
"""

from __future__ import annotations

import time

from fastapi import HTTPException, Request, status

from app.config import Settings, get_settings
from shared.token_bucket import TokenBucketLimiter


class RateLimiter:
    """Dependency invocable de FastAPI que aplica un token bucket por IP."""

    def __init__(self, limiter: TokenBucketLimiter) -> None:
        self._limiter = limiter

    @classmethod
    def from_settings(cls, settings: Settings) -> "RateLimiter":
        return cls(
            TokenBucketLimiter(
                capacity=settings.rate_limit_capacity,
                refill_per_sec=settings.rate_limit_refill_per_sec,
            )
        )

    @staticmethod
    def _client_ip(request: Request) -> str:
        if request.client is not None and request.client.host:
            return request.client.host
        return "unknown"

    def __call__(self, request: Request) -> None:
        key = self._client_ip(request)
        now_ms = int(time.time() * 1000)
        if not self._limiter.allow(key, now_ms):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )


# Limiter por defecto, a nivel de proceso, construido desde la configuración.
# Las rutas dependen de esta instancia; los tests la sobrescriben vía
# `app.dependency_overrides[rate_limiter]`.
rate_limiter = RateLimiter.from_settings(get_settings())
