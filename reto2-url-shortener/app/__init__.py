"""Reto 2 · Acortador de URLs (FastAPI + SQLite).

Este paquete depende del paquete ``shared/`` del monorepo. Cuando el servicio se
lanza desde la carpeta de este reto (``uvicorn app.main:app``), la raíz del
monorepo no está en ``sys.path``, así que la añadimos aquí. Esto mantiene el
one-liner documentado funcionando sin necesidad de instalar ``shared`` como
paquete. (Los tests añaden la raíz vía ``pythonpath`` en pyproject.toml, así que
aquí es un no-op.)
"""

from __future__ import annotations

import os
import sys

_MONOREPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _MONOREPO_ROOT not in sys.path:
    sys.path.insert(0, _MONOREPO_ROOT)
