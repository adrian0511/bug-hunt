from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    """Hora UTC actual como datetime naive.

    SQLite no preserva la información de zona horaria, así que una columna
    escrita como tz-aware se lee de vuelta naive. Para evitar mezclar
    datetimes aware/naive (que rompe al comparar), estandarizamos en UTC naive
    en todo el código.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ShortURL(Base):
    """Una URL acortada y sus metadatos.

    ``code`` es el identificador público usado en el enlace corto. Para un alias
    personalizado equivale al alias; en caso contrario es una cadena
    auto-generada. ``is_custom`` distingue ambos casos para que la deduplicación
    por URL sólo reutilice entradas auto-generadas (un alias personalizado nunca
    se reutiliza silenciosamente para otra petición distinta).
    """

    __tablename__ = "short_urls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False, index=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    def is_expired(self, *, now: datetime | None = None) -> bool:
        """Devuelve True si esta URL tiene un TTL que ya ha transcurrido."""
        if self.expires_at is None:
            return False
        now = now or _utcnow()
        return now >= self.expires_at
