"""
Puertos del marco: plantilla para tableros que vienen de una foto.

La foto no lee los puertos, así que un tablero fotografiado arranca con una
plantilla que el usuario confirma o corrige. La plantilla reparte los 9 puertos a
lo largo de la costa con el patrón simétrico del marco del juego base: separaciones
de 3, 3 y 4 aristas, tres veces (3+3+4 = 10, y 3 × 10 = 30 aristas de costa).

Es una aproximación estándar, no la copia de un marco concreto: las posiciones y los
tipos exactos se confirman contra el tablero físico.
"""

from __future__ import annotations

import math
from collections import Counter

from app.domain.tablero import PUERTOS, todas_las_aristas

#: Posiciones de los 9 puertos sobre las 30 aristas de costa, en orden.
_POSICIONES = [0, 3, 6, 10, 13, 16, 20, 23, 26]

#: Tipos por defecto, en el orden de las posiciones. Se confirman a mano.
TIPOS_POR_DEFECTO = [
    "3:1", "trigo", "mineral", "3:1", "oveja", "3:1", "3:1", "ladrillo", "madera",
]

#: Aristas que avanza la plantilla por cada giro de 60° (30 aristas / 6 lados).
_ARISTAS_POR_GIRO = 5


def _centro(hexagono: tuple[int, int]) -> tuple[float, float]:
    """Centro de un hexágono en el plano (punta arriba), como en el frontend."""
    q, r = hexagono
    return math.sqrt(3) * (q + r / 2), 1.5 * r


def _punto_medio(arista: frozenset) -> tuple[float, float]:
    """Punto medio de una arista: promedio de los centros de sus vértices."""
    puntos = []
    for vertice in arista:
        centros = [_centro(h) for h in vertice]
        puntos.append((sum(c[0] for c in centros) / 3, sum(c[1] for c in centros) / 3))
    return (puntos[0][0] + puntos[1][0]) / 2, (puntos[0][1] + puntos[1][1]) / 2


def es_de_costa(arista: frozenset, hexagonos: set) -> bool:
    """De los dos hexágonos que comparten sus vértices, exactamente uno es tierra."""
    v1, v2 = tuple(arista)
    return len((v1 & v2) & hexagonos) == 1


def aristas_de_costa_en_orden(hexagonos) -> list[frozenset]:
    """
    Las aristas de costa, ordenadas alrededor del tablero en sentido horario,
    empezando por la de arriba.
    """
    en_tablero = set(hexagonos)
    costa = [a for a in todas_las_aristas() if es_de_costa(a, en_tablero)]

    def angulo(arista: frozenset) -> float:
        x, y = _punto_medio(arista)
        # atan2 con el eje y hacia abajo (como en pantalla): 0 arriba, luego horario.
        return (math.atan2(x, -y)) % (2 * math.pi)

    return sorted(costa, key=angulo)


def plantilla_de_puertos(hexagonos, giro: int = 0) -> dict[frozenset, str]:
    """
    Los 9 puertos de la plantilla, como los guarda el dominio: arista → tipo.

    Parameters
    ----------
    giro : int
        Cuántas veces rotar la plantilla 60° en sentido horario.
    """
    costa = aristas_de_costa_en_orden(hexagonos)
    desplazamiento = (giro * _ARISTAS_POR_GIRO) % len(costa)
    return {
        costa[(p + desplazamiento) % len(costa)]: tipo
        for p, tipo in zip(_POSICIONES, TIPOS_POR_DEFECTO, strict=True)
    }


def verificar_puertos(puertos: dict[frozenset, str], hexagonos) -> list[str]:
    """
    Avisos sobre los puertos frente al juego base. Devuelve avisos en vez de lanzar:
    el usuario puede estar a mitad de corregirlos.
    """
    avisos = []
    if len(puertos) != 9:
        avisos.append(f"Hay {len(puertos)} puertos; el juego base lleva 9.")
    if Counter(puertos.values()) != Counter(PUERTOS):
        avisos.append(
            "El reparto de puertos no es el del juego base: 4 de 3:1 y uno 2:1 de cada recurso."
        )
    en_tablero = set(hexagonos)
    if any(not es_de_costa(a, en_tablero) for a in puertos):
        avisos.append("Hay un puerto que no está en la costa.")
    vertices = [v for arista in puertos for v in arista]
    if len(vertices) != len(set(vertices)):
        avisos.append("Dos puertos comparten un vértice.")
    return avisos
