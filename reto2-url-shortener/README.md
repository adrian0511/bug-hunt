# Reto 2 · Acortador de URLs

Servicio HTTP (FastAPI + SQLite) con arquitectura modular por *feature*.
Reutiliza el mismo `TokenBucketLimiter` del Reto 1 para el rate limit por IP.

## Arquitectura

Organización **por módulo/feature**, no por capa horizontal. Un recurso nuevo
(ej. `users`) se añade como `app/modules/users/` sin tocar `urls`.

```
app/
├── main.py                 # crea la app, incluye api_router, registra handlers
├── config.py               # Settings (Pydantic Settings) vía env vars
├── database.py             # engine/session SQLAlchemy (SQLite), Base
├── api/v1/api.py           # router raíz que agrupa los módulos (versionado)
├── core/
│   ├── exceptions.py       # excepciones de dominio + handlers (400/404/409/410)
│   └── rate_limiter.py     # dependency que envuelve shared/token_bucket (429)
└── modules/urls/
    ├── router.py           # capa HTTP: recibe request → llama service → schema
    ├── services.py         # lógica de negocio (lanza excepciones de dominio)
    ├── models.py           # ORM ShortURL
    ├── schemas.py          # DTOs Pydantic (contratos de la API)
    └── dependencies.py     # get_db, get_url_service
```

### Flujo de una request

```
             ┌──────────┐   schema in   ┌───────────┐   session    ┌─────────┐
 HTTP  ─────▶│ router.py │ ────────────▶ │ services  │ ───────────▶ │ model   │
             │ (HTTP)    │               │ (negocio) │              │ (ORM)   │
 HTTP  ◀─────│           │ ◀──────────── │           │ ◀─────────── │ SQLite  │
             └──────────┘   schema out   └───────────┘   ORM obj    └─────────┘
                   ▲                           │
                   │ rate_limiter (429)        │ lanza excepción de dominio
                   │ (core)                    ▼
                   └──────────────  exception handlers (core) ── 400/404/409/410
```

El router **no** contiene lógica de negocio: sólo traduce entre HTTP y el
service. El service **nunca** lanza `HTTPException`: lanza excepciones de
dominio (`app/core/exceptions.py`) que los handlers globales convierten al
status code correcto.

## Puesta en marcha

```bash
python -m pip install -r requirements.txt
cp .env.example .env            # opcional: todos los valores tienen default
uvicorn app.main:app --reload   # http://localhost:8000
```

> El servicio depende del paquete `shared/` del monorepo. `app/__init__.py`
> añade la raíz del monorepo a `sys.path`, de modo que `uvicorn app.main:app`
> funciona tal cual desde esta carpeta, sin instalar nada extra.

Docs interactivas: <http://localhost:8000/docs>.

## Checklist de verificación con `curl`

Asume el servidor en `http://localhost:8000`.

### 🟢 Nivel Base

```bash
# POST /shorten → 201 {code, short}
curl -i -X POST localhost:8000/shorten \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/hello"}'
# → HTTP/1.1 201 Created
# → {"code":"Ab3xK9z","short":"http://localhost:8000/Ab3xK9z"}

# GET /{code} → 302 con header Location
curl -i localhost:8000/Ab3xK9z
# → HTTP/1.1 302 Found
# → location: https://example.com/hello

# 404 si el code no existe
curl -i localhost:8000/noexiste
# → HTTP/1.1 404 Not Found

# 400 si la URL es inválida (esquema/host); FastAPI daría 422, el handler → 400
curl -i -X POST localhost:8000/shorten \
  -H 'Content-Type: application/json' -d '{"url":"ftp://nope"}'
# → HTTP/1.1 400 Bad Request
```

### 🟡 Nivel Medio

```bash
# Idempotencia: misma url (sin alias) → mismo code. La 1ª llamada 201, las
# repeticiones devuelven el recurso existente con 200.
curl -s -X POST localhost:8000/shorten -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/idem"}'        # 201, code X
curl -s -X POST localhost:8000/shorten -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/idem"}'        # 200, mismo code X

# Alias personalizado
curl -i -X POST localhost:8000/shorten -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","alias":"promo"}'
# → 201 {"code":"promo", ...}

# Alias duplicado → 409
curl -i -X POST localhost:8000/shorten -H 'Content-Type: application/json' \
  -d '{"url":"https://otra.com","alias":"promo"}'
# → HTTP/1.1 409 Conflict

# GET /stats/{code} → clics + metadata
curl -s localhost:8000/stats/promo
# → {"code":"promo","url":"https://example.com","clicks":0,
#    "created_at":"...","expires_at":null}
```

### 🔴 Nivel Avanzado

```bash
# TTL: pasado el tiempo, GET /{code} → 410
CODE=$(curl -s -X POST localhost:8000/shorten -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/efimera","ttl":2}' | python -c "import sys,json;print(json.load(sys.stdin)['code'])")
curl -i localhost:8000/$CODE          # dentro de 2s → 302
sleep 2.1
curl -i localhost:8000/$CODE          # → HTTP/1.1 410 Gone

# Persistencia real: reinicia el proceso (Ctrl-C y de nuevo uvicorn) y el code
# sigue existiendo — los datos viven en ./data/urlshortener.db (SQLite en disco).

# Rate limit por IP → 429 al excederse (config por env RATE_LIMIT_CAPACITY /
# RATE_LIMIT_REFILL_PER_SEC). Con una capacidad baja, un burst lo dispara:
for i in $(seq 1 100); do
  curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/promo
done | sort | uniq -c
# → verás una mezcla de 302 y, al agotar el cubo, 429.
```

## Decisiones de diseño (no triviales)

- **Status de la idempotencia (200 vs 201).** La primera vez que se acorta una
  URL se crea el recurso → `201 Created`. Las repeticiones de la *misma* URL
  (sin alias) devuelven el recurso ya existente → `200 OK` (no se crea nada
  nuevo). El `code` es siempre el mismo. El service devuelve `(obj, created)` y
  el router fija el status según `created`.

- **Alias vs deduplicación por URL.** La deduplicación idempotente sólo aplica a
  entradas **auto-generadas** (`is_custom=False`). Un alias personalizado nunca
  se reutiliza para otra request ni participa en el dedup por URL: si pides un
  alias que ya existe obtienes `409`, aunque apunte a otra URL. Así el usuario
  siempre obtiene exactamente el alias que pidió, o un error claro.

- **Cálculo de la expiración (TTL).** `expires_at = created_at + ttl` (segundos)
  en el momento de la creación; si no hay `ttl`, queda `NULL` (no expira nunca).
  `GET /{code}` compara contra `now` y devuelve `410` si ya pasó. Una entrada
  auto-generada **expirada no se reutiliza** en el dedup: una nueva petición de
  la misma URL genera un code nuevo. `GET /stats/{code}` sí funciona sobre codes
  expirados (puedes seguir inspeccionando sus métricas).

- **Sin prefijo `/api/v1` pese al agrupador versionado.** `app/api/v1/api.py`
  existe como *seam* de versionado/organización (donde se enganchan los futuros
  módulos), pero el router de `urls` se monta **sin prefix** y `main.py` incluye
  el `api_router` **sin prefix**, de modo que las rutas públicas quedan
  exactamente en `/shorten`, `/{code}` y `/stats/{code}`, como pide el enunciado.

- **Datetimes naive UTC.** SQLite no preserva zona horaria, así que un
  `DateTime` escrito como *aware* se lee *naive*. Para no mezclar aware/naive
  (que rompe las comparaciones), se estandariza en **UTC naive** en todo el
  código (`models._utcnow`).

- **SQLite y concurrencia.** `connect_args={"check_same_thread": False}` +
  una sesión corta por request (`get_db` en `dependencies.py`) para poder servir
  desde el thread pool de FastAPI sin conflictos.

- **Rate limiter compartido.** `core/rate_limiter.py` no reimplementa el
  algoritmo: envuelve `shared/token_bucket/bucket.py` (`TokenBucketLimiter`),
  keyeando por IP. Es una dependency de FastAPI inyectada en todas las rutas del
  módulo; al agotarse el cubo lanza `HTTPException(429)` (esto es capa HTTP, por
  eso aquí sí se usa `HTTPException` y no una excepción de dominio).

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

- `tests/modules/urls/test_services.py`: unitarios de la lógica de negocio
  (idempotencia, alias, TTL, expiración, validación de URL, clics).
- `tests/modules/urls/test_router.py`: integración vía `TestClient` (base, medio
  y avanzado, incluyendo un test dedicado al `429`).
- `tests/conftest.py`: SQLite in-memory aislada por test y rate limiter
  permisivo por defecto (el test del `429` instala uno estricto).

## Docker (bonus)

Sin `docker-compose` (no hay DB externa). El contexto de build es la **raíz del
monorepo** porque la imagen necesita `shared/`:

```bash
# desde retos-backend/
docker build -f reto2-url-shortener/Dockerfile -t url-shortener .
docker run -p 8000:8000 -v "$PWD/reto2-url-shortener/data:/app/data" url-shortener
```
