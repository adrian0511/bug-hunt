from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# Alias personalizados: letras, dígitos, guion y guion bajo, 1..64 caracteres.
_ALIAS_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


class ShortenRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL de destino (http/https).")
    alias: str | None = Field(
        default=None,
        pattern=_ALIAS_PATTERN,
        description="Alias personalizado opcional usado como código corto.",
    )
    ttl: int | None = Field(
        default=None,
        gt=0,
        description="Time-to-live opcional en segundos.",
    )


class ShortenResponse(BaseModel):
    code: str
    short: str


class StatsResponse(BaseModel):
    # Lee los atributos directamente del objeto ORM.
    model_config = ConfigDict(from_attributes=True)

    code: str
    url: str
    clicks: int
    created_at: datetime
    expires_at: datetime | None = None
