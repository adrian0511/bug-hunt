# Reto 1 · Rate limiter (token bucket)

Filtro `stdin → stdout`. Lee una configuración y una lista de peticiones, y
emite `ALLOW` o `DENY` por cada petición según un **token bucket** por *key*.

## Formato de entrada

```
capacity refillPerSec        <- primera línea (no vacía)
timestamp_ms key             <- una petición por línea (timestamps no decrecientes)
...
```

## Formato de salida

Una línea `ALLOW` o `DENY` por cada línea de petición, en el mismo orden.

## Comportamiento

- Cada `key` tiene su propio cubo que **empieza lleno** (`capacity` tokens).
- Se rellena de forma continua a `refillPerSec` tokens/seg, con tope en
  `capacity` (nunca desborda).
- Cada petición consume 1 token: si hay ≥ 1 → `ALLOW` (resta 1); si no → `DENY`.
- El relleno es **perezoso** (lazy): se calcula según el tiempo transcurrido
  desde la última petición de esa key. Sin threads ni timers.
- Soporta refills fraccionarios (tokens internos en `float`).

La lógica del cubo NO está aquí: vive en
[`../shared/token_bucket/bucket.py`](../shared/token_bucket/bucket.py)
(`TokenBucketLimiter.allow(key, now_ms) -> bool`), reutilizada por el Reto 2.
Este reto sólo aporta el parseo `stdin → stdout`
([`src/rate_limiter/cli.py`](src/rate_limiter/cli.py)).

## Uso

```bash
python main.py < ejemplo_input.txt
```

Ejemplo (`capacity=2`, `refillPerSec=1`):

```
$ python main.py < ejemplo_input.txt
ALLOW
ALLOW
DENY
DENY
ALLOW
```

También acepta entrada por pipe:

```bash
printf '2 1\n0 a\n0 a\n0 a\n500 a\n1000 a\n' | python main.py
```

Detalles del ejemplo (`capacity=2`, `refillPerSec=1`):

| Petición   | Tokens antes | Refill | Tokens | Veredicto |
|------------|--------------|--------|--------|-----------|
| `0 a`      | 2.0          | +0.0   | 2 → 1  | ALLOW     |
| `0 a`      | 1.0          | +0.0   | 1 → 0  | ALLOW     |
| `0 a`      | 0.0          | +0.0   | 0      | DENY      |
| `500 a`    | 0.0          | +0.5   | 0.5    | DENY      |
| `1000 a`   | 0.5          | +0.5   | 1 → 0  | ALLOW     |

## Casos borde soportados

- Líneas en blanco (se ignoran) e input vacío (sin salida).
- `refillPerSec=0`: una key drenada nunca se recupera.
- Keys independientes entre sí.
- El relleno nunca excede `capacity`.
- Timestamps no crecientes (no se concede relleno negativo).

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Cubre: el caso de ejemplo exacto (bucket y filtro), keys independientes, tope de
`capacity`, `refillPerSec=0`, refills fraccionarios, validación de parámetros
inválidos, y el filtro completo (stdin → stdout) con líneas vacías e input
vacío.
