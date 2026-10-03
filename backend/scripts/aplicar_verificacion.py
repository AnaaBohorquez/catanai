"""
Aplica a ``app/domain/reglas.md`` la verificación hecha en la página «Reglas de Catan
por verificar»: marca cada regla revisada como ``verificado: sí``, anota su fuente
(sección y página del reglamento) y, si se corrigió, reemplaza su texto.

Uso, desde ``backend/``, con los resultados copiados de la página en un archivo::

    uv run python -m scripts.aplicar_verificacion resultados.json

Después, reinicia el backend: las reglas se leen una vez por proceso.
"""

from __future__ import annotations

import json
import re
import sys
import textwrap
from pathlib import Path

from app.domain.reglas import RUTA_REGLAS


def aplicar(contenido: str, resultados: list[dict]) -> tuple[str, list[str]]:
    """
    El archivo con las reglas revisadas actualizadas, y los ids que no existían.

    Solo toca las entradas de ``resultados``; el resto queda igual.
    """
    desconocidos = []
    for r in resultados:
        # Las tres líneas de cabecera, sin cruzar saltos de línea; el texto, hasta la
        # siguiente entrada. Con ".*" en la cabecera y re.S, la búsqueda se comía las
        # reglas siguientes.
        patron = re.compile(
            rf"^## {re.escape(r['id'])}\n(temas:[^\n]*)\nfuente:[^\n]*\n"
            rf"verificado:[^\n]*\n(.*?)(?=^## |\Z)",
            re.M | re.S,
        )
        m = patron.search(contenido)
        if m is None:
            desconocidos.append(r["id"])
            continue
        texto = m.group(2)
        if r.get("estado") == "corregida" and r.get("texto"):
            texto = "\n" + textwrap.fill(r["texto"].strip(), width=85) + "\n\n"
        bloque = (
            f"## {r['id']}\n{m.group(1)}\nfuente: {r.get('fuente', '').strip()}\n"
            f"verificado: sí\n{texto}"
        )
        contenido = contenido[: m.start()] + bloque + contenido[m.end():]
    return contenido, desconocidos


def main() -> None:
    crudo = Path(sys.argv[1]).read_text(encoding="utf-8")
    # La página antepone una línea de título; el JSON empieza en el primer "[".
    resultados = json.loads(crudo[crudo.index("["):])
    nuevo, desconocidos = aplicar(RUTA_REGLAS.read_text(encoding="utf-8"), resultados)
    RUTA_REGLAS.write_text(nuevo, encoding="utf-8")
    print(f"Actualizadas {len(resultados) - len(desconocidos)} reglas en {RUTA_REGLAS.name}.")
    if desconocidos:
        print("No existen:", ", ".join(desconocidos))


if __name__ == "__main__":
    main()
