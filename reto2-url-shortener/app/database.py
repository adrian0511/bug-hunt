from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""


def _make_engine(database_url: str):
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        _ensure_sqlite_dir(database_url)
    return create_engine(database_url, connect_args=connect_args)


def _ensure_sqlite_dir(database_url: str) -> None:
    """Crea el directorio padre de una DB SQLite en archivo si hace falta."""
    # sqlite:///./data/urlshortener.db  ->  ./data/urlshortener.db
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return
    path = database_url[len(prefix):]
    if path in ("", ":memory:"):
        return
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Crea todas las tablas. Importa los modelos para que se registren en ``Base.metadata``."""
    # Importado por el efecto secundario de registrar el modelo en Base.metadata.
    from app.modules.urls import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
