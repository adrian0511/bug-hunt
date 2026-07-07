# Bug-Hunt

Monorepo con dos retos técnicos independientes que comparten un mismo algoritmo
de rate limiting (token bucket).

```
├── shared/token_bucket/     # Única implementación del token bucket (reutilizada)
├── reto1-rate-limiter/      # Filtro stdin → stdout (ALLOW/DENY por línea)
└── reto2-url-shortener/     # Servicio HTTP FastAPI + SQLite
```

El algoritmo del token bucket vive **una sola vez** en
[`shared/token_bucket/bucket.py`](shared/token_bucket/bucket.py) como la clase
`TokenBucketLimiter`. El Reto 1 lo usa por *key* de petición; el Reto 2 lo
envuelve en una dependency de FastAPI para limitar por IP. No hay duplicación
del algoritmo entre retos.

## Requisitos

- Python 3.11+ (desarrollado y probado con 3.12)

## Quickstart

### Reto 1 · Rate limiter (token bucket)

```bash
cd reto1-rate-limiter
python -m pip install -r requirements.txt      # solo dependencias de test
python main.py < ejemplo_input.txt             # o:  echo "..." | python main.py
```

Ver [reto1-rate-limiter/README.md](reto1-rate-limiter/README.md).

### Reto 2 · Acortador de URLs

```bash
cd reto2-url-shortener
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Ver [reto2-url-shortener/README.md](reto2-url-shortener/README.md).

## Correr los tests

Cada reto tiene su propia suite de pytest. El `pyproject.toml` de cada reto
añade la raíz del monorepo al `pythonpath`, de modo que `import` de
`shared.token_bucket` funciona desde ambos.

```bash
# Reto 1
cd reto1-rate-limiter && python -m pytest -q

# Reto 2
cd reto2-url-shortener && python -m pytest -q
```

O ambos de una:

```bash
python -m pytest reto1-rate-limiter reto2-url-shortener -q
```

## Nota sobre el rate limiter compartido

`TokenBucketLimiter.allow(key, now_ms) -> bool`:

- Cada `key` tiene su propio cubo que empieza lleno (`capacity` tokens).
- Se rellena de forma **perezosa** (lazy) según el tiempo transcurrido desde la
  última petición de esa key — sin threads ni timers en background.
- Refills fraccionarios (tokens en `float`), con tope en `capacity`.
- Cada petición aceptada consume 1 token; si no hay ≥ 1 → denegada.
