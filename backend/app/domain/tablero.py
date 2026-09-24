"""
tablero.py
==========
Generador de tableros válidos de Catan (juego base, 4 jugadores).

Representación
--------------
- Un hexágono se identifica con coordenadas axiales (q, r).
  El tablero son los 19 pares con |q| <= 2, |r| <= 2 y |q + r| <= 2,
  lo que reproduce la forma de filas 3-4-5-4-3.

- Un vértice se identifica por el CONJUNTO de los tres hexágonos que toca,
  como un frozenset de coordenadas. Algunos de esos hexágonos caen fuera
  del tablero (son mar); eso es justo lo que distingue un vértice de la
  orilla de uno del interior.

- Una arista se identifica por el conjunto de sus dos vértices.

Esta representación evita cualquier cálculo geométrico: la adyacencia,
los pips y la regla de distancia salen de operaciones entre conjuntos.
"""

from __future__ import annotations

import random
from collections import Counter

# ---------------------------------------------------------------------------
# Constantes del juego base
# ---------------------------------------------------------------------------

#: Las seis direcciones axiales, en orden cíclico alrededor de un hexágono.
DIRECCIONES = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

#: Cuántos hexágonos hay de cada terreno. Suman 19.
TERRENOS = {
    "bosque": 4,    # produce madera
    "pastos": 4,    # produce oveja
    "campos": 4,    # produce trigo
    "colinas": 3,   # produce ladrillo
    "montanas": 3,  # produce mineral
    "desierto": 1,  # no produce nada
}

#: Qué recurso da cada terreno.
RECURSO_DE_TERRENO = {
    "bosque": "madera",
    "pastos": "oveja",
    "campos": "trigo",
    "colinas": "ladrillo",
    "montanas": "mineral",
    "desierto": None,
}

RECURSOS = ["madera", "ladrillo", "trigo", "oveja", "mineral"]

#: Las 18 fichas numéricas del juego base.
FICHAS = [2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12]

#: Pips de cada número: en cuántas de las 36 combinaciones de dos dados sale.
PIPS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}

#: Los 9 puertos: 4 genéricos y 5 específicos, uno por recurso.
PUERTOS = ["3:1", "3:1", "3:1", "3:1", "madera", "ladrillo", "trigo", "oveja", "mineral"]

#: Costo de cada construcción, en recursos.
COSTOS = {
    "camino": {"madera": 1, "ladrillo": 1},
    "poblado": {"madera": 1, "ladrillo": 1, "trigo": 1, "oveja": 1},
    "ciudad": {"trigo": 2, "mineral": 3},
    "carta_desarrollo": {"trigo": 1, "oveja": 1, "mineral": 1},
}


# ---------------------------------------------------------------------------
# Topología: qué hexágonos, vértices y aristas existen
# ---------------------------------------------------------------------------

def coordenadas_hexagonos() -> list[tuple[int, int]]:
    """Devuelve las 19 coordenadas axiales del tablero, en orden de lectura."""
    coords = []
    for r in range(-2, 3):
        for q in range(-2, 3):
            if abs(q + r) <= 2:
                coords.append((q, r))
    return coords


def vecinos(hexagono: tuple[int, int]) -> list[tuple[int, int]]:
    """Los seis hexágonos adyacentes, en orden cíclico (pueden ser mar)."""
    q, r = hexagono
    return [(q + dq, r + dr) for dq, dr in DIRECCIONES]


def vertices_de_hexagono(hexagono: tuple[int, int]) -> list[frozenset]:
    """
    Las seis esquinas de un hexágono.

    Cada esquina es el conjunto formado por el hexágono y dos de sus vecinos
    consecutivos en el orden cíclico.
    """
    vs = vecinos(hexagono)
    return [
        frozenset({hexagono, vs[i], vs[(i + 1) % 6]})
        for i in range(6)
    ]


def todos_los_vertices() -> list[frozenset]:
    """Los 54 vértices del tablero, ordenados de forma determinista."""
    vistos = set()
    for h in coordenadas_hexagonos():
        vistos.update(vertices_de_hexagono(h))
    return sorted(vistos, key=lambda v: sorted(v))


def todas_las_aristas() -> list[frozenset]:
    """
    Las 72 aristas del tablero.

    Dos vértices forman arista si comparten exactamente dos hexágonos.
    """
    vertices = todos_los_vertices()
    aristas = set()
    for i, a in enumerate(vertices):
        for b in vertices[i + 1:]:
            if len(a & b) == 2:
                aristas.add(frozenset({a, b}))
    return sorted(aristas, key=lambda e: sorted(sorted(v) for v in e))


def vertices_adyacentes(vertice: frozenset, vertices: list[frozenset]) -> list[frozenset]:
    """Los vértices que comparten arista con este. Sirve para la regla de distancia."""
    return [v for v in vertices if v != vertice and len(v & vertice) == 2]


# ---------------------------------------------------------------------------
# Generación de un tablero aleatorio válido
# ---------------------------------------------------------------------------

def _seis_y_ocho_adyacentes(terrenos, numeros, hexes) -> bool:
    """True si algún 6 u 8 toca a otro 6 u 8 (colocación no recomendada)."""
    rojos = {h for h in hexes if numeros.get(h) in (6, 8)}
    for h in rojos:
        for vecino in vecinos(h):
            if vecino in rojos:
                return True
    return False


def generar_tablero(semilla: int | None = None, evitar_rojos_juntos: bool = True) -> dict:
    """
    Genera un tablero aleatorio válido.

    Parameters
    ----------
    semilla : int, opcional
        Fija el azar para que el tablero sea reproducible.
    evitar_rojos_juntos : bool
        Si es True, rebaraja hasta que ningún 6 u 8 quede junto a otro 6 u 8,
        que es la colocación que recomienda el reglamento.

    Returns
    -------
    dict con las llaves:
        'hexagonos' : lista de las 19 coordenadas
        'terrenos'  : {coordenada -> nombre del terreno}
        'recursos'  : {coordenada -> recurso o None}
        'numeros'   : {coordenada -> ficha numérica} (el desierto no aparece)
        'pips'      : {coordenada -> pips} (el desierto vale 0)
        'puertos'   : {arista -> tipo de puerto}
        'semilla'   : la semilla usada
    """
    rng = random.Random(semilla)
    hexes = coordenadas_hexagonos()

    bolsa_terrenos = [t for t, n in TERRENOS.items() for _ in range(n)]

    for _ in range(1000):
        rng.shuffle(bolsa_terrenos)
        terrenos = dict(zip(hexes, bolsa_terrenos))

        # Las fichas numéricas se reparten entre los hexágonos que no son desierto.
        fichas = FICHAS.copy()
        rng.shuffle(fichas)
        sin_desierto = [h for h in hexes if terrenos[h] != "desierto"]
        numeros = dict(zip(sin_desierto, fichas))

        if not evitar_rojos_juntos:
            break
        if not _seis_y_ocho_adyacentes(terrenos, numeros, hexes):
            break
    else:
        raise RuntimeError("No se encontró una colocación válida en 1000 intentos")

    pips = {h: PIPS[numeros[h]] if h in numeros else 0 for h in hexes}
    recursos = {h: RECURSO_DE_TERRENO[terrenos[h]] for h in hexes}
    puertos = _colocar_puertos(rng, hexes)

    return {
        "hexagonos": hexes,
        "terrenos": terrenos,
        "recursos": recursos,
        "numeros": numeros,
        "pips": pips,
        "puertos": puertos,
        "semilla": semilla,
    }


def _colocar_puertos(rng: random.Random, hexes: list[tuple[int, int]]) -> dict:
    """
    Reparte los 9 puertos en aristas de la costa, sin que dos compartan vértice.

    Una arista es de costa si de los dos hexágonos que la definen, exactamente
    uno pertenece al tablero (el otro es mar).
    """
    en_tablero = set(hexes)
    costeras = []
    for arista in todas_las_aristas():
        v1, v2 = tuple(arista)
        compartidos = v1 & v2
        if len(compartidos & en_tablero) == 1:
            costeras.append(arista)

    rng.shuffle(costeras)
    elegidas, ocupados = [], set()
    for arista in costeras:
        vs = set(arista)
        if vs & ocupados:
            continue
        elegidas.append(arista)
        ocupados |= vs
        if len(elegidas) == 9:
            break

    tipos = PUERTOS.copy()
    rng.shuffle(tipos)
    return dict(zip(elegidas, tipos))


# ---------------------------------------------------------------------------
# Consultas sobre un vértice
# ---------------------------------------------------------------------------

def hexagonos_del_vertice(vertice: frozenset, tablero: dict) -> list[tuple[int, int]]:
    """Los hexágonos del vértice que sí están en el tablero (entre 1 y 3)."""
    en_tablero = set(tablero["hexagonos"])
    return sorted(vertice & en_tablero)


def pips_del_vertice(vertice: frozenset, tablero: dict) -> int:
    """Suma de pips de los hexágonos que toca el vértice."""
    return sum(tablero["pips"][h] for h in hexagonos_del_vertice(vertice, tablero))


def pips_por_recurso(vertice: frozenset, tablero: dict) -> dict[str, int]:
    """Pips que aporta el vértice, desglosados por recurso."""
    salida = {r: 0 for r in RECURSOS}
    for h in hexagonos_del_vertice(vertice, tablero):
        recurso = tablero["recursos"][h]
        if recurso is not None:
            salida[recurso] += tablero["pips"][h]
    return salida


def puerto_del_vertice(vertice: frozenset, tablero: dict) -> str | None:
    """El tipo de puerto al que da acceso el vértice, si toca alguno."""
    for arista, tipo in tablero["puertos"].items():
        if vertice in arista:
            return tipo
    return None


# ---------------------------------------------------------------------------
# Verificación
# ---------------------------------------------------------------------------

def verificar_tablero(tablero: dict) -> None:
    """Lanza AssertionError si el tablero no cumple las reglas del juego base."""
    hexes = tablero["hexagonos"]
    assert len(hexes) == 19, f"Se esperaban 19 hexágonos, hay {len(hexes)}"

    conteo = Counter(tablero["terrenos"].values())
    assert conteo == Counter(TERRENOS), f"Reparto de terrenos incorrecto: {conteo}"

    assert len(tablero["numeros"]) == 18, "Deben ser 18 fichas numéricas"
    assert sorted(tablero["numeros"].values()) == sorted(FICHAS), "Fichas incorrectas"

    desiertos = [h for h, t in tablero["terrenos"].items() if t == "desierto"]
    assert all(h not in tablero["numeros"] for h in desiertos), "El desierto no lleva ficha"

    assert sum(tablero["pips"].values()) == 58, "El total de pips del juego base es 58"
    assert len(tablero["puertos"]) == 9, "Deben ser 9 puertos"


if __name__ == "__main__":
    vertices = todos_los_vertices()
    aristas = todas_las_aristas()

    print(f"Hexágonos: {len(coordenadas_hexagonos())}")
    print(f"Vértices:  {len(vertices)}")
    print(f"Aristas:   {len(aristas)}")

    tablero = generar_tablero(semilla=42)
    verificar_tablero(tablero)
    print("\nTablero de ejemplo (semilla 42) verificado.\n")

    ranking = sorted(vertices, key=lambda v: pips_del_vertice(v, tablero), reverse=True)
    print("Los 5 vértices con más pips:")
    for v in ranking[:5]:
        hs = hexagonos_del_vertice(v, tablero)
        detalle = ", ".join(
            f"{tablero['terrenos'][h]}-{tablero['numeros'].get(h, 'x')}" for h in hs
        )
        puerto = puerto_del_vertice(v, tablero)
        extra = f" | puerto {puerto}" if puerto else ""
        print(f"  {pips_del_vertice(v, tablero):2d} pips  [{detalle}]{extra}")
