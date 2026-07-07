from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.api import api_router
from app.core.exceptions import register_exception_handlers
from app.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Asegura que el esquema de SQLite exista antes de servir peticiones.
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="URL Shortener",
        version="1.0.0",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    # Montado sin prefijo -> rutas públicas: /shorten, /{code}, /stats/{code}.
    app.include_router(api_router)
    return app


app = create_app()
