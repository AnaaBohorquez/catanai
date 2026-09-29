"""
Visión sobre una segunda foto: fichas pequeñas (unos 12 px de radio en 545 px).

Con ella se detectó que el detector tomaba círculos falsos grandes como tamaño típico
y no encontraba ninguna ficha. La imagen no se versiona (``logs/``); si no está, se
salta. Ojo: NO es un tablero base legal (el desierto lleva un 10 y hay tres 9), así
que aquí solo se exigen terrenos y el aviso, no los números.
"""

from __future__ import annotations

import pytest

from app.core.config import RAIZ
from app.services import vision

FOTO = RAIZ / "logs" / "ejemplo-catan-2.png"

# fmt: off
TERRENOS = [
    "colinas", "bosque", "pastos",
    "bosque", "campos", "montanas", "campos",
    "pastos", "montanas", "pastos", "pastos", "bosque",
    "desierto", "colinas", "campos", "colinas",
    "montanas", "bosque", "campos",
]
# fmt: on

pytestmark = pytest.mark.skipif(not FOTO.exists(), reason="foto 2 no disponible")


@pytest.fixture(scope="module")
def lectura():
    return vision.leer_tablero(FOTO.read_bytes())


def test_encuentra_las_fichas_pequenas_y_lee_los_19_terrenos(lectura):
    assert [d.terreno for d in lectura.detecciones] == TERRENOS


def test_avisa_que_el_desierto_tiene_ficha(lectura):
    assert any("desierto parece tener una ficha" in a for a in lectura.avisos)


def test_ofrece_opciones_para_revisar(lectura):
    for d in lectura.detecciones:
        if d.terreno == "desierto":
            continue
        # El terreno elegido está entre los dos que más se parecen por color.
        assert d.terreno in d.opciones_terreno[:2]
        assert len(d.opciones_numero) == 10
