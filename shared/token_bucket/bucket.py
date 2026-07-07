from __future__ import annotations

from dataclasses import dataclass

# Tolerancia para absorber el redondeo de punto flotante cuando los tokens se
# acumulan a lo largo de muchos refills fraccionarios (p. ej.
# 0.3 + 0.3 + 0.3 + 0.1 == 0.9999999999999999). Un cubo que en aritmética exacta
# llegaría justo a 1 token debe seguir devolviendo ALLOW. El epsilon sólo afecta
# a valores dentro de 1e-9 de un token entero, así que nunca convierte un cubo
# genuinamente sub-token en un allow.
_EPSILON = 1e-9


@dataclass
class _Bucket:
    """Estado por key: tokens actuales y última vez que se tocó el cubo."""

    tokens: float
    last_ms: int


class TokenBucketLimiter:
    """Limiter de token bucket con relleno perezoso, indexado por una key.

    Cada key tiene su propio cubo que empieza lleno (``capacity`` tokens) y se
    rellena de forma continua a ``refill_per_sec`` tokens/segundo, con tope en
    ``capacity`` (nunca desborda). Cada petición aceptada consume un token.

    Args:
        capacity: Número máximo de tokens que puede contener un cubo. Debe ser > 0.
        refill_per_sec: Tokens añadidos por segundo. Debe ser >= 0 (0 significa
            que una key nunca se recupera una vez drenada).

    Raises:
        ValueError: Si ``capacity`` <= 0 o ``refill_per_sec`` < 0.
    """

    def __init__(self, capacity: float, refill_per_sec: float) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0, got {capacity!r}")
        if refill_per_sec < 0:
            raise ValueError(
                f"refill_per_sec must be >= 0, got {refill_per_sec!r}"
            )

        self._capacity = float(capacity)
        self._refill_per_sec = float(refill_per_sec)
        self._buckets: dict[str, _Bucket] = {}

    @property
    def capacity(self) -> float:
        return self._capacity

    @property
    def refill_per_sec(self) -> float:
        return self._refill_per_sec

    def allow(self, key: str, now_ms: int) -> bool:
        """Devuelve ``True`` si la petición se permite (se consumió un token).

        Args:
            key: Identificador del cubo (p. ej. una API key o una IP de cliente).
            now_ms: Tiempo actual en milisegundos. Se espera que los timestamps
                de una misma key sean no decrecientes; un reloj que retrocede se
                acota (ni relleno negativo ni viajes en el tiempo).

        Returns:
            ``True`` y consume un token cuando hay al menos un token disponible;
            en caso contrario ``False`` y no consume nada.
        """
        bucket = self._buckets.get(key)
        if bucket is None:
            # Una key nueva empieza con el cubo lleno.
            bucket = _Bucket(tokens=self._capacity, last_ms=now_ms)
            self._buckets[key] = bucket
        else:
            self._refill(bucket, now_ms)

        if bucket.tokens >= 1.0 - _EPSILON:
            bucket.tokens -= 1.0
            return True
        return False

    def _refill(self, bucket: _Bucket, now_ms: int) -> None:
        """Rellena ``bucket`` según el tiempo transcurrido desde la última vez."""
        elapsed_ms = now_ms - bucket.last_ms
        if elapsed_ms <= 0:
            # Mismo instante (o timestamp no creciente): no hay nada que añadir,
            # pero mantenemos last_ms monótono para no conceder nunca un relleno
            # de tiempo negativo.
            bucket.last_ms = max(bucket.last_ms, now_ms)
            return

        refill = (elapsed_ms / 1000.0) * self._refill_per_sec
        bucket.tokens = min(self._capacity, bucket.tokens + refill)
        bucket.last_ms = now_ms
