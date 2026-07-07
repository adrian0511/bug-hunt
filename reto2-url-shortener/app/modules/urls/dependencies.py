from __future__ import annotations

from typing import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.modules.urls.services import UrlService


def get_db() -> Iterator[Session]:
    """Genera una sesión de DB de vida corta, una por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_url_service(db: Session = Depends(get_db)) -> UrlService:
    """Provee un UrlService ligado a la sesión de DB de la request."""
    return UrlService(db)
