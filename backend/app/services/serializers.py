"""
Traducción entre el dominio y la API.

El dominio representa un vértice como un ``frozenset`` de coordenadas, que es lo
que hace simple toda la geometría. Pero eso no viaja por JSON, así que la API usa
un identificador de texto estable y esta capa convierte en ambos sentidos.
"""

from __future__ import annotations

from collections import Counter

from app.domain.puertos import verificar_puertos
from app.domain.tablero import (
    FICHAS,
    PIPS,
    RECURSO_DE_TERRENO,
    TERRENOS,
    puerto_del_vertice,
    todas_las_aristas,
    todos_los_vertices,
)

#: Identificador de texto -> vértice del dominio. Se calcula una sola vez.
_VERTICES = todos_los_vertices()


def id_vertice(vertice: frozenset) -> str:
    """Identificador estable de un vértice, por ejemplo ``-1,0|0,-1|0,0``."""
    return "|".join(f"{q},{r}" for q, r in sorted(vertice))


_POR_ID = {id_vertice(v): v for v in _VERTICES}


def vertice_desde_id(identificador: str) -> frozenset:
    """Recupera el vértice a partir de su identificador."""
    if identificador not in _POR_ID:
        raise KeyError(f"Vértice desconocido: {identificador}")
    return _POR_ID[identificador]


def id_hexagono(coordenada: tuple[int, int]) -> str:
    """Identificador de un hexágono, por ejemplo ``0,-2``."""
    return f"{coordenada[0]},{coordenada[1]}"


def hexagono_desde_id(identificador: str) -> tuple[int, int]:
    q, r = identificador.split(",")
    return int(q), int(r)


def tablero_a_api(tablero: dict) -> dict:
    """Convierte un tablero del dominio al formato que viaja por JSON."""
    return {
        "hexagonos": [
            {
                "id": id_hexagono(c),
                "q": c[0],
                "r": c[1],
                "terreno": tablero["terrenos"][c],
                "recurso": tablero["recursos"][c],
                "numero": tablero["numeros"].get(c),
                "pips": tablero["pips"][c],
            }
            for c in tablero["hexagonos"]
        ],
        "puertos": [
            {"vertices": sorted(id_vertice(v) for v in arista), "tipo": tipo}
            for arista, tipo in tablero["puertos"].items()
        ],
        "vertices": [
            {
                "id": id_vertice(v),
                "hexagonos": sorted(id_hexagono(h) for h in v),
                "puerto": puerto_del_vertice(v, tablero),
            }
            for v in _VERTICES
        ],
        "aristas": [
            {"vertices": sorted(id_vertice(v) for v in arista)}
            for arista in todas_las_aristas()
        ],
    }


def tablero_desde_api(datos: dict) -> dict:
    """
    Reconstruye un tablero del dominio a partir de lo que manda el cliente.

    Solo se leen los hexágonos y los puertos: el resto de la estructura (vértices,
    aristas, pips) se deriva, y derivarla evita que el cliente pueda mandar un
    tablero internamente inconsistente.
    """
    terrenos, numeros = {}, {}
    for hexagono in datos["hexagonos"]:
        coord = (int(hexagono["q"]), int(hexagono["r"]))
        terrenos[coord] = hexagono["terreno"]
        numero = hexagono.get("numero")
        if numero is not None and hexagono["terreno"] != "desierto":
            numeros[coord] = int(numero)

    puertos = {}
    for puerto in datos.get("puertos", []):
        arista = frozenset(vertice_desde_id(v) for v in puerto["vertices"])
        puertos[arista] = puerto["tipo"]

    return {
        "hexagonos": sorted(terrenos, key=lambda c: (c[1], c[0])),
        "terrenos": terrenos,
        "numeros": numeros,
        "recursos": {c: RECURSO_DE_TERRENO[t] for c, t in terrenos.items()},
        "pips": {c: PIPS[numeros[c]] if c in numeros else 0 for c in terrenos},
        "puertos": puertos,
        "semilla": datos.get("semilla"),
    }


def avisos_del_tablero(tablero: dict) -> list[str]:
    """
    Revisa el tablero contra las reglas del juego base.

    Devuelve avisos en vez de lanzar una excepción: el usuario puede estar a mitad
    de capturar su tablero, o jugar con una variante, y en ese caso conviene
    advertir sin bloquear el cálculo.
    """
    avisos = []
    if len(tablero["hexagonos"]) != 19:
        avisos.append(
            f"Hay {len(tablero['hexagonos'])} hexágonos; el juego base lleva 19."
        )
    desiertos = sum(1 for t in tablero["terrenos"].values() if t == "desierto")
    if desiertos != 1:
        avisos.append(f"Hay {desiertos} desiertos; el juego base lleva 1.")
    if len(tablero["numeros"]) != 18:
        avisos.append(
            f"Hay {len(tablero['numeros'])} fichas numéricas; el juego base lleva 18."
        )
    total = sum(tablero["pips"].values())
    if tablero["numeros"] and total != 58:
        avisos.append(f"Los pips suman {total}; en el juego base suman 58.")

    # Los totales no bastan: 5 campos y 2 colinas siguen siendo 19 hexágonos, y
    # dos 12 sin ningún 2 suman los mismos pips. Hay que comparar el reparto.
    terrenos = Counter(tablero["terrenos"].values())
    distintos = [
        f"{t} {terrenos.get(t, 0)} de {n}" for t, n in TERRENOS.items()
        if t != "desierto" and terrenos.get(t, 0) != n
    ]
    if distintos:
        avisos.append(
            "El reparto de terrenos no es el del juego base: " + ", ".join(distintos) + "."
        )
    fichas = Counter(tablero["numeros"].values())
    if len(tablero["numeros"]) == 18 and fichas != Counter(FICHAS):
        avisos.append("Las fichas no son las del juego base: algún número sobra o falta.")

    avisos.extend(verificar_puertos(tablero["puertos"], tablero["hexagonos"]))
    return avisos
