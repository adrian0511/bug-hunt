from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import RedirectResponse

from app.core.rate_limiter import rate_limiter
from app.modules.urls.dependencies import get_url_service
from app.modules.urls.schemas import ShortenRequest, ShortenResponse, StatsResponse
from app.modules.urls.services import UrlService

router = APIRouter(dependencies=[Depends(rate_limiter)])


@router.post(
    "/shorten",
    response_model=ShortenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crea (o reutiliza) una URL corta",
)
def shorten(
    payload: ShortenRequest,
    response: Response,
    service: UrlService = Depends(get_url_service),
) -> ShortenResponse:
    short_url, created = service.create_short_url(
        url=str(payload.url),
        alias=payload.alias,
        ttl=payload.ttl,
    )
    # Las repeticiones idempotentes de la misma URL devuelven el recurso
    # existente con 200; un recurso recién creado devuelve 201.
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return ShortenResponse(
        code=short_url.code,
        short=service.build_short_link(short_url.code),
    )


@router.get(
    "/stats/{code}",
    response_model=StatsResponse,
    summary="Número de clics y metadatos de un código",
)
def stats(
    code: str,
    service: UrlService = Depends(get_url_service),
) -> StatsResponse:
    short_url = service.get_stats(code)
    return StatsResponse.model_validate(short_url)


@router.get(
    "/{code}",
    status_code=status.HTTP_302_FOUND,
    summary="Redirige a la URL de destino",
    response_class=RedirectResponse,
)
def redirect(
    code: str,
    service: UrlService = Depends(get_url_service),
) -> RedirectResponse:
    short_url = service.get_for_redirect(code)
    return RedirectResponse(
        url=short_url.url,
        status_code=status.HTTP_302_FOUND,
    )
