"""
Calibra los rangos de color de la visión con una foto real del tablero.

Los `RANGOS` de `services/vision.py` se estimaron a ojo. Este script toma una foto y
los 19 terrenos correctos, recorta cada hexágono con las mismas funciones que usa la
visión, mide los colores reales y propone rangos nuevos. No modifica nada: imprime
los rangos propuestos y los aciertos antes y después, y tú decides si copiarlos.

Uso, desde ``backend/``::

    uv run python -m scripts.calibrar_vision foto.jpg \\
        --terrenos "bosque,pastos,campos, ..."   # 19, en orden de lectura

El orden de lectura es fila por fila, de arriba abajo y de izquierda a derecha
(3, 4, 5, 4 y 3 hexágonos), igual que `coordenadas_hexagonos()`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from app.domain.tablero import coordenadas_hexagonos
from app.services import vision, vision_fichas

TERRENOS = list(vision.RANGOS)

#: Percentiles que definen cada rango: dejan fuera el 5 % de píxeles raros de cada
#: lado (reflejos, sombras, bordes de la ficha).
PERCENTIL_BAJO, PERCENTIL_ALTO = 5, 95


def _parches(imagen_bytes: bytes) -> tuple[dict, bool]:
    """
    Los píxeles HSV de cada hexágono, tomados como lo hace la visión: el anillo entre
    la ficha y el borde de la pieza, sobre la red ajustada con las fichas. Si no se
    encuentran fichas, el parche del método de respaldo (borde del tablero).
    """
    imagen = vision._decodificar(imagen_bytes)
    hsv_imagen = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    seguras, radio = vision_fichas.detectar_fichas(imagen, hsv_imagen)
    red = vision_fichas.ajustar_red(seguras, radio, hsv_imagen)
    salida = {}
    if red is not None:
        for coord in coordenadas_hexagonos():
            pixeles = vision_fichas.pixeles_de_terreno(imagen, red, coord).astype(np.uint8)
            hsv = cv2.cvtColor(pixeles.reshape(1, -1, 3), cv2.COLOR_BGR2HSV)
            salida[coord] = hsv.reshape(-1, 3)
        return salida, True
    rectificada, encontrado = vision._rectificar(imagen)
    for coord in coordenadas_hexagonos():
        parche = vision._parche_del_hexagono(rectificada, coord)
        pixeles = parche.reshape(-1, 3).astype(np.uint8)
        hsv = cv2.cvtColor(pixeles.reshape(1, -1, 3), cv2.COLOR_BGR2HSV)
        salida[coord] = hsv.reshape(-1, 3)
    return salida, encontrado


def _aciertos(parches: dict, correctos: dict, rangos: dict) -> float:
    original = vision.RANGOS
    vision.RANGOS = rangos
    try:
        bien = 0
        for coord, hsv in parches.items():
            bgr = cv2.cvtColor(hsv.reshape(1, -1, 3), cv2.COLOR_HSV2BGR).reshape(-1, 3)
            terreno, _ = vision._clasificar_terreno(bgr)
            bien += terreno == correctos[coord]
        return bien / len(parches)
    finally:
        vision.RANGOS = original


def proponer_rangos(parches: dict, correctos: dict) -> dict:
    """Para cada terreno, los percentiles 5–95 de H, S y V de sus hexágonos."""
    rangos = dict(vision.RANGOS)
    for terreno in TERRENOS:
        juntos = [parches[c] for c, t in correctos.items() if t == terreno]
        if not juntos:
            continue  # sin ejemplos en esta foto: se conserva el rango anterior
        pixeles = np.concatenate(juntos)
        rangos[terreno] = {
            canal: (
                int(np.percentile(pixeles[:, i], PERCENTIL_BAJO)),
                int(np.percentile(pixeles[:, i], PERCENTIL_ALTO)),
            )
            for i, canal in enumerate(("h", "s", "v"))
        }
    return rangos


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibra los colores de la visión.")
    parser.add_argument("foto", type=Path)
    parser.add_argument("--terrenos", required=True,
                        help="19 terrenos separados por comas, en orden de lectura")
    args = parser.parse_args()

    lista = [t.strip() for t in args.terrenos.split(",")]
    if len(lista) != 19 or any(t not in TERRENOS for t in lista):
        raise SystemExit(f"Hacen falta 19 terrenos de: {', '.join(TERRENOS)}")
    correctos = dict(zip(coordenadas_hexagonos(), lista, strict=True))

    parches, encontrado = _parches(args.foto.read_bytes())
    if not encontrado:
        print("AVISO: no encontré las fichas ni el borde; los recortes pueden estar mal.")

    propuestos = proponer_rangos(parches, correctos)
    antes = _aciertos(parches, correctos, vision.RANGOS)
    despues = _aciertos(parches, correctos, propuestos)
    print(f"Aciertos con los rangos actuales:   {antes:.0%}")
    print(f"Aciertos con los rangos propuestos: {despues:.0%}")
    print("\nRANGOS propuestos (cópialos a services/vision.py si mejoran):")
    for terreno, rango in propuestos.items():
        print(f'    "{terreno}": {{"h": {rango["h"]}, "s": {rango["s"]}, "v": {rango["v"]}}},')


if __name__ == "__main__":
    main()
