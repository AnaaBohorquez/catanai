"""
partida.py
==========
Lo que produce el usuario a mitad de partida: todos sus poblados y ciudades.

En la colocación inicial se razona sobre una pareja de vértices; aquí, sobre todas
las piezas que el usuario marcó. Una ciudad cobra dos cartas donde un poblado cobra
una, así que sus pips cuentan doble.
"""

from __future__ import annotations

from app.domain.tablero import (
    PIPS,
    RECURSOS,
    hexagonos_del_vertice,
    pips_por_recurso,
    puerto_del_vertice,
)
from app.domain.variables import turnos_hasta

#: Piezas de cada jugador en el juego base.
MAX_POBLADOS = 5
MAX_CIUDADES = 4


def produccion(poblados: list[frozenset], ciudades: list[frozenset], tablero: dict) -> dict:
    """Pips por recurso de todas tus piezas; las ciudades cuentan doble."""
    total = {r: 0 for r in RECURSOS}
    for piezas, factor in ((poblados, 1), (ciudades, 2)):
        for v in piezas:
            for r, pips in pips_por_recurso(v, tablero).items():
                total[r] += factor * pips
    return total


def numeros_que_pagan(
    poblados: list[frozenset], ciudades: list[frozenset], tablero: dict
) -> dict[int, dict[str, int]]:
    """Número de dados → cartas de cada recurso que cobras cuando sale."""
    salida: dict[int, dict[str, int]] = {}
    for piezas, factor in ((poblados, 1), (ciudades, 2)):
        for v in piezas:
            for h in hexagonos_del_vertice(v, tablero):
                numero = tablero["numeros"].get(h)
                recurso = tablero["recursos"].get(h)
                if numero is None or recurso is None:
                    continue
                cartas = salida.setdefault(numero, {})
                cartas[recurso] = cartas.get(recurso, 0) + factor
    return dict(sorted(salida.items(), key=lambda par: -PIPS[par[0]]))


def puertos_de(piezas: list[frozenset], tablero: dict) -> set[str]:
    """Los puertos a los que dan acceso tus poblados y ciudades."""
    return {p for v in piezas if (p := puerto_del_vertice(v, tablero)) is not None}


def resumen(
    poblados: list[frozenset], ciudades: list[frozenset], tablero: dict, jugadores: int = 4
) -> dict:
    """
    Todo lo que el chat necesita para aconsejar a mitad de partida.

    Las rondas hasta cada construcción usan la misma fórmula que las variables del
    modelo (``variables.turnos_hasta``), con la producción de todas tus piezas.
    """
    pips = produccion(poblados, ciudades, tablero)
    puertos = puertos_de([*poblados, *ciudades], tablero)
    return {
        "pips_por_recurso": pips,
        "cartas_por_ronda": {r: round(pips[r] / 36 * jugadores, 2) for r in RECURSOS},
        "no_produces": [r for r in RECURSOS if pips[r] == 0],
        "numeros_que_pagan": numeros_que_pagan(poblados, ciudades, tablero),
        "puertos": sorted(puertos),
        "rondas_hasta": {
            pieza: round(rondas, 1)
            for pieza, rondas in turnos_hasta(pips, puertos, jugadores).items()
        },
        "piezas": {"poblados": len(poblados), "ciudades": len(ciudades)},
        "quedan": {
            "poblados": MAX_POBLADOS - len(poblados),
            "ciudades": MAX_CIUDADES - len(ciudades),
        },
    }
