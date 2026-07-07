from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # URL de conexión de SQLAlchemy. Por defecto: una DB SQLite en archivo bajo
    # ./data para que los datos sobrevivan a reinicios (requisito del nivel
    # avanzado).
    database_url: str = "sqlite:///./data/urlshortener.db"

    # URL base pública usada para construir el enlace `short` devuelto.
    base_url: str = "http://localhost:8000"

    # Longitud de los códigos cortos auto-generados.
    code_length: int = 7

    # Rate limit por IP (token bucket). `capacity` tokens por IP, rellenados a
    # `refill_per_sec` tokens/segundo. Los defaults son permisivos para uso normal.
    rate_limit_capacity: float = 60
    rate_limit_refill_per_sec: float = 10


@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia de Settings cacheada (leída una vez por proceso)."""
    return Settings()
