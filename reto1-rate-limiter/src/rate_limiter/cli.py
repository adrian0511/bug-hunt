from __future__ import annotations

from typing import IO, Iterable, Iterator

from shared.token_bucket import TokenBucketLimiter


def _non_empty_lines(lines: Iterable[str]) -> Iterator[str]:
    """Genera las líneas sin espacios, omitiendo las vacías o sólo-espacios."""
    for line in lines:
        stripped = line.strip()
        if stripped:
            yield stripped


def _parse_config(line: str) -> tuple[float, float]:
    """Parsea la línea de cabecera ``capacity refillPerSec``."""
    parts = line.split()
    if len(parts) != 2:
        raise ValueError(
            "config line must be 'capacity refillPerSec', "
            f"got {line!r}"
        )
    capacity = float(parts[0])
    refill_per_sec = float(parts[1])
    return capacity, refill_per_sec


def _parse_request(line: str) -> tuple[int, str]:
    """Parsea una línea de petición ``timestamp_ms key``."""
    parts = line.split(maxsplit=1)
    if len(parts) != 2:
        raise ValueError(
            f"request line must be 'timestamp_ms key', got {line!r}"
        )
    timestamp_ms = int(parts[0])
    key = parts[1]
    return timestamp_ms, key


def process(lines: Iterable[str]) -> Iterator[str]:
    """Convierte las líneas de entrada en veredictos ``ALLOW``/``DENY``, perezosamente.

    La primera línea no vacía configura el limiter; cada línea no vacía
    siguiente es una petición. Genera un veredicto por petición.
    """
    it = _non_empty_lines(lines)

    first = next(it, None)
    if first is None:
        # Entrada vacía → sin config, sin salida.
        return

    capacity, refill_per_sec = _parse_config(first)
    limiter = TokenBucketLimiter(capacity=capacity, refill_per_sec=refill_per_sec)

    for line in it:
        timestamp_ms, key = _parse_request(line)
        yield "ALLOW" if limiter.allow(key, timestamp_ms) else "DENY"


def run(stdin: IO[str], stdout: IO[str]) -> None:
    """Lee las peticiones de ``stdin`` y escribe los veredictos en ``stdout``."""
    for verdict in process(stdin):
        stdout.write(f"{verdict}\n")
