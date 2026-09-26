"""
Exporta el contrato de la API a ``openapi.json`` en la raíz del repositorio.

Se escribe desde Python y no con una redirección de la terminal: en Windows
PowerShell 5.1, ``>`` guarda en UTF-16 y los acentos llegan rotos al generador de
tipos del frontend.

Uso, desde ``backend/``::

    uv run python -m scripts.exportar_openapi
"""

from __future__ import annotations

import json

from app.core.config import RAIZ
from app.main import app

DESTINO = RAIZ / "openapi.json"


def main() -> None:
    contrato = app.openapi()
    DESTINO.write_text(
        json.dumps(contrato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Contrato escrito en {DESTINO} ({len(contrato['paths'])} rutas)")


if __name__ == "__main__":
    main()
