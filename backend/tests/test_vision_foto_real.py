"""
Visión sobre la foto de referencia del tablero de principiantes.

La imagen tiene derechos de autor y no se versiona: vive en ``logs/`` (ignorada por
git). Si no está, estas pruebas se saltan; la visión queda cubierta igual por la
prueba sintética de ``test_vision_fichas.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import RAIZ
from app.services import vision

FOTO = RAIZ / "logs" / "ejemplo-tablero.png"

#: Lo que hay en la foto, fila por fila (3, 4, 5, 4 y 3 hexágonos).
# fmt: off
VERDAD = [
    ("campos", 9), ("campos", 4), ("pastos", 5),
    ("pastos", 6), ("bosque", 5), ("colinas", 6), ("montanas", 10),
    ("colinas", 10), ("bosque", 11), ("campos", 2), ("colinas", 3), ("pastos", 11),
    ("montanas", 8), ("pastos", 9), ("bosque", 4), ("bosque", 12),
    ("desierto", None), ("montanas", 3), ("campos", 8),
]
# fmt: on

pytestmark = pytest.mark.skipif(not FOTO.exists(), reason="foto de referencia no disponible")


@pytest.fixture(scope="module")
def lectura():
    return vision.leer_tablero(Path(FOTO).read_bytes())


def test_acierta_los_19_terrenos(lectura):
    leidos = [d.terreno for d in lectura.detecciones]
    assert leidos == [t for t, _ in VERDAD]


def test_acierta_los_18_numeros(lectura):
    leidos = [d.numero for d in lectura.detecciones]
    assert leidos == [n for _, n in VERDAD]


def test_ningun_error_llega_con_confianza_alta(lectura):
    for d, (_, n) in zip(lectura.detecciones, VERDAD, strict=True):
        if d.numero != n:
            assert d.confianza_numero < 0.5, d.id


def _girada(grados: float) -> bytes:
    import cv2
    import numpy as np

    imagen = cv2.imdecode(np.frombuffer(FOTO.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    alto, ancho = imagen.shape[:2]
    matriz = cv2.getRotationMatrix2D((ancho / 2, alto / 2), grados, 1.0)
    cos, sen = abs(matriz[0, 0]), abs(matriz[0, 1])
    nuevo_ancho, nuevo_alto = int(alto * sen + ancho * cos), int(alto * cos + ancho * sen)
    matriz[0, 2] += nuevo_ancho / 2 - ancho / 2
    matriz[1, 2] += nuevo_alto / 2 - alto / 2
    girada = cv2.warpAffine(
        imagen, matriz, (nuevo_ancho, nuevo_alto), borderValue=(255, 255, 255)
    )
    return cv2.imencode(".png", girada)[1].tobytes()


@pytest.mark.parametrize("grados", [180, 90, 25])
def test_lee_la_foto_girada(grados):
    """
    Girada, la lectura sale con el tablero rotado (es el mismo tablero): se compara
    como conjunto de parejas terreno-número, que no depende de la rotación.
    """
    lectura = vision.leer_tablero(_girada(grados))
    leidas = sorted((d.terreno, d.numero or 0) for d in lectura.detecciones)
    assert leidas == sorted((t, n or 0) for t, n in VERDAD)
    assert all(
        d.confianza_numero < 0.5 or (d.terreno, d.numero) in VERDAD
        for d in lectura.detecciones
    )


@pytest.mark.parametrize("calidad", [95, 85, 70])
def test_aguanta_la_recompresion_jpeg(calidad):
    """
    El navegador reenvía la foto como JPEG. En una foto tan pequeña (fichas de unos
    17 px de radio) la compresión movía agujeros y dígitos; la lectura debe seguir
    acertando y, sobre todo, no dar ningún número equivocado como seguro.
    """
    import cv2
    import numpy as np

    # cv2.imread no abre rutas con acentos en Windows ("Actuaría"): se decodifican bytes.
    imagen = cv2.imdecode(np.frombuffer(FOTO.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    datos = cv2.imencode(".jpg", imagen, [cv2.IMWRITE_JPEG_QUALITY, calidad])[1].tobytes()
    lectura = vision.leer_tablero(datos)
    assert [d.terreno for d in lectura.detecciones] == [t for t, _ in VERDAD]
    pares = list(zip(lectura.detecciones, VERDAD, strict=True))
    for d, (_, n) in pares:
        if d.numero != n:
            assert d.confianza_numero < 0.5, (calidad, d.id)
    assert sum(d.numero == n for d, (_, n) in pares if n) >= 16
