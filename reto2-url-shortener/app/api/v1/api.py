"""Router raíz que agrupa el router de cada módulo de feature.

Este es el punto de versionado de la API: los recursos nuevos (p. ej. ``users``)
se añaden aquí como nuevos módulos bajo ``app/modules/`` sin tocar los módulos
existentes.

NOTA: el router de ``urls`` se monta **sin prefijo** para que las rutas públicas
queden exactamente en ``/shorten``, ``/{code}`` y ``/stats/{code}`` como exige el
enunciado — el agrupador versionado existe por organización, no para añadir un
segmento de ruta ``/api/v1``.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.urls.router import router as urls_router

api_router = APIRouter()
api_router.include_router(urls_router, tags=["urls"])
