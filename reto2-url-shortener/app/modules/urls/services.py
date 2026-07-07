from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.exceptions import (
    AliasAlreadyExistsError,
    InvalidUrlError,
    ShortUrlExpiredError,
    ShortUrlNotFoundError,
)
from app.modules.urls.models import ShortURL, _utcnow

_CODE_ALPHABET = string.ascii_letters + string.digits
_MAX_CODE_ATTEMPTS = 10


class UrlService:
    """Orquesta la creación y búsqueda de URLs cortas para una única request."""

    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()

    # -- creación --------------------------------------------------------

    def create_short_url(
        self,
        url: str,
        alias: str | None = None,
        ttl: int | None = None,
    ) -> tuple[ShortURL, bool]:
        """Crea (o reutiliza) una URL corta.

        Devuelve ``(short_url, created)`` donde ``created`` es False cuando se
        reutilizó una entrada existente vía deduplicación idempotente.

        Raises:
            InvalidUrlError: si ``url`` no es una URL http/https válida.
            AliasAlreadyExistsError: si ``alias`` ya está en uso.
        """
        url = self._validate_url(url)
        expires_at = self._compute_expiry(ttl)

        if alias is not None:
            return self._create_with_alias(url, alias, expires_at), True

        # Sin alias: dedup idempotente por URL entre entradas auto-generadas y vivas.
        existing = self._find_reusable(url)
        if existing is not None:
            return existing, False

        return self._create_generated(url, expires_at), True

    def _create_with_alias(
        self, url: str, alias: str, expires_at: datetime | None
    ) -> ShortURL:
        if self._get_by_code(alias) is not None:
            raise AliasAlreadyExistsError(f"Alias '{alias}' already exists")
        short_url = ShortURL(
            code=alias,
            url=url,
            is_custom=True,
            expires_at=expires_at,
        )
        return self._persist(short_url)

    def _create_generated(
        self, url: str, expires_at: datetime | None
    ) -> ShortURL:
        code = self._generate_unique_code()
        short_url = ShortURL(
            code=code,
            url=url,
            is_custom=False,
            expires_at=expires_at,
        )
        return self._persist(short_url)

    def _find_reusable(self, url: str) -> ShortURL | None:
        """Devuelve una entrada existente auto-generada y no expirada para ``url``."""
        stmt = select(ShortURL).where(
            ShortURL.url == url,
            ShortURL.is_custom.is_(False),
        )
        for candidate in self._db.scalars(stmt):
            if not candidate.is_expired():
                return candidate
        return None

    # -- búsqueda --------------------------------------------------------

    def get_for_redirect(self, code: str) -> ShortURL:
        """Obtiene una URL viva e incrementa su contador de clics.

        Raises:
            ShortUrlNotFoundError: si ninguna URL tiene ese código.
            ShortUrlExpiredError: si el TTL de la URL ha transcurrido.
        """
        short_url = self._require(code)
        if short_url.is_expired():
            raise ShortUrlExpiredError(f"Short URL '{code}' has expired")
        short_url.clicks += 1
        self._db.commit()
        self._db.refresh(short_url)
        return short_url

    def get_stats(self, code: str) -> ShortURL:
        """Devuelve los metadatos de un código (funciona aunque esté expirado).

        Raises:
            ShortUrlNotFoundError: si ninguna URL tiene ese código.
        """
        return self._require(code)

    # -- helpers ---------------------------------------------------------

    def _require(self, code: str) -> ShortURL:
        short_url = self._get_by_code(code)
        if short_url is None:
            raise ShortUrlNotFoundError(f"Short URL '{code}' not found")
        return short_url

    def _get_by_code(self, code: str) -> ShortURL | None:
        stmt = select(ShortURL).where(ShortURL.code == code)
        return self._db.scalars(stmt).first()

    def _persist(self, short_url: ShortURL) -> ShortURL:
        self._db.add(short_url)
        self._db.commit()
        self._db.refresh(short_url)
        return short_url

    def _generate_unique_code(self) -> str:
        length = self._settings.code_length
        for _ in range(_MAX_CODE_ATTEMPTS):
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
            if self._get_by_code(code) is None:
                return code
        raise RuntimeError(
            "Could not generate a unique code; consider increasing code_length"
        )

    def _compute_expiry(self, ttl: int | None) -> datetime | None:
        if ttl is None:
            return None
        return _utcnow() + timedelta(seconds=ttl)

    @staticmethod
    def _validate_url(url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise InvalidUrlError(f"Invalid URL: {url!r}")
        return url

    def build_short_link(self, code: str) -> str:
        """Construye el enlace corto público de un código desde la base URL configurada."""
        base = self._settings.base_url.rstrip("/")
        return f"{base}/{code}"
