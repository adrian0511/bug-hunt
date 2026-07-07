"""Excepciones de dominio y los handlers globales que las mapean a respuestas HTTP.

Los services lanzan estas excepciones de dominio; nunca lanzan ``HTTPException``
directamente. Los handlers registrados por ``register_exception_handlers``
traducen cada excepción de dominio al status code correcto:

    InvalidUrlError          -> 400
    ShortUrlNotFoundError    -> 404
    ShortUrlExpiredError     -> 410
    AliasAlreadyExistsError  -> 409

Los errores de validación de request de Pydantic/FastAPI (que por defecto son
422) también se traducen a 400, como exige el nivel base.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Clase base de los errores de dominio. Lleva un status HTTP y un mensaje."""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidUrlError(DomainError):
    """La URL proporcionada no es una URL http/https válida con host."""

    status_code = status.HTTP_400_BAD_REQUEST


class ShortUrlNotFoundError(DomainError):
    """No existe ninguna URL corta para el código dado."""

    status_code = status.HTTP_404_NOT_FOUND


class ShortUrlExpiredError(DomainError):
    """La URL corta existe pero su TTL ya ha transcurrido."""

    status_code = status.HTTP_410_GONE


class AliasAlreadyExistsError(DomainError):
    """El alias personalizado solicitado ya está en uso."""

    status_code = status.HTTP_409_CONFLICT


def _error_body(message: str) -> dict:
    return {"detail": message}


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los handlers globales que traducen errores de dominio/validación a HTTP."""

    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # El nivel base exige que la entrada inválida (422 por defecto) se
        # exponga como 400.
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": "Invalid request",
                "errors": jsonable_encoder(exc.errors()),
            },
        )
