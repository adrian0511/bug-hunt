from __future__ import annotations

import os
import sys

# Hace importables tanto la raíz del monorepo (para `shared`) como el `src` de
# este reto cuando se ejecuta como script suelto (`python main.py`), sin
# necesidad de instalar nada.
_HERE = os.path.dirname(os.path.abspath(__file__))
_MONOREPO_ROOT = os.path.dirname(_HERE)
for _path in (_MONOREPO_ROOT, os.path.join(_HERE, "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from rate_limiter.cli import run  # noqa: E402  (tras configurar sys.path)


def main() -> None:
    run(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
