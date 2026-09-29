"""
expansion.py
============
Hacia dónde crecer después de la colocación inicial: los mejores vértices para el
tercer poblado.

No usa la regresión: el modelo se entrenó para elegir la pareja inicial, no el
tercer poblado. Aquí el puntaje es una fórmula a la vista, término por término,
para que cada destino se pueda explicar ("suma 9 pips, te da mineral que no
producías, está a 2 caminos"). Los pesos son a criterio, no aprendidos de datos.
"""

from __future__ import annotations

from collections import deque

from app.domain.simulador import TOPOLOGIA
from app.domain.tablero import (
    RECURSOS,
    pips_del_vertice,
    pips_por_recurso,
    puerto_del_vertice,
)

#: Pesos de la fórmula. Ver ``puntuar_destino``.
PESO_RECURSO_NUEVO = 0.5
BONO_PUERTO_DOMINANTE = 3.0
BONO_PUERTO_GENERICO = 1.0
CASTIGO_POR_CAMINO_EXTRA = 2.0
CASTIGO_RIVAL_CERCA = 2.0

#: Un poblado nuevo necesita al menos 2 caminos: la regla de distancia prohíbe los
#: vértices vecinos de un poblado.
CAMINOS_MINIMOS = 2


def rutas_desde(
    propios: list[frozenset], rivales: list[frozenset], max_caminos: int
) -> dict[frozenset, list[frozenset]]:
    """
    La ruta más corta (en caminos) desde tus poblados a cada vértice alcanzable.

    Búsqueda en anchura por las aristas del tablero. Un camino no puede cruzar un
    poblado rival, así que esos vértices no se atraviesan.

    Returns
    -------
    dict
        Vértice → ruta, del poblado de salida al vértice (incluidos ambos).
    """
    bloqueados = set(rivales)
    rutas: dict[frozenset, list[frozenset]] = {v: [v] for v in propios}
    cola = deque(propios)
    while cola:
        actual = cola.popleft()
        if len(rutas[actual]) - 1 >= max_caminos:
            continue
        for vecino in TOPOLOGIA.adyacentes[actual]:
            if vecino in rutas or vecino in bloqueados:
                continue
            rutas[vecino] = [*rutas[actual], vecino]
            cola.append(vecino)
    return rutas


def es_legal(vertice: frozenset, poblados: list[frozenset]) -> bool:
    """Libre y sin ningún poblado (tuyo o rival) a una arista: la regla de distancia."""
    return vertice not in poblados and not any(
        p in TOPOLOGIA.adyacentes[vertice] for p in poblados
    )


def puntuar_destino(
    vertice: frozenset,
    ruta: list[frozenset],
    propios: list[frozenset],
    rivales: list[frozenset],
    tablero: dict,
) -> dict:
    """
    El puntaje de un destino y su desglose.

    puntaje = pips del vértice
            + 0.5 × pips de los recursos que tus poblados no producen
            + 3 si tiene puerto 2:1 de tu recurso dominante (1 si es 3:1)
            − 2 por cada camino más allá de 2
            − 2 si un rival está a 2 aristas o menos (puede ganarte el vértice)
    """
    produccion = {r: 0 for r in RECURSOS}
    for p in propios:
        for r, pips in pips_por_recurso(p, tablero).items():
            produccion[r] += pips
    dominante = max(RECURSOS, key=lambda r: produccion[r])

    propios_del_vertice = pips_por_recurso(vertice, tablero)
    nuevos = [r for r in RECURSOS if produccion[r] == 0 and propios_del_vertice.get(r, 0) > 0]
    pips_nuevos = sum(propios_del_vertice[r] for r in nuevos)

    puerto = puerto_del_vertice(vertice, tablero)
    if puerto == dominante:
        bono_puerto = BONO_PUERTO_DOMINANTE
    elif puerto == "3:1":
        bono_puerto = BONO_PUERTO_GENERICO
    else:
        bono_puerto = 0.0

    caminos = len(ruta) - 1
    rival_cerca = any(
        r in TOPOLOGIA.adyacentes[vertice]
        or any(r in TOPOLOGIA.adyacentes[v] for v in TOPOLOGIA.adyacentes[vertice])
        for r in rivales
    )

    desglose = {
        "pips": float(pips_del_vertice(vertice, tablero)),
        "recursos_nuevos": PESO_RECURSO_NUEVO * pips_nuevos,
        "puerto": bono_puerto,
        "caminos_extra": -CASTIGO_POR_CAMINO_EXTRA * max(0, caminos - CAMINOS_MINIMOS),
        "rival_cerca": -CASTIGO_RIVAL_CERCA if rival_cerca else 0.0,
    }
    return {
        "vertice": vertice,
        "ruta": ruta,
        "caminos": caminos,
        "pips": int(desglose["pips"]),
        "recursos_nuevos": nuevos,
        "puerto": puerto,
        "puerto_dominante": puerto == dominante,
        "riesgo_rival": rival_cerca,
        "puntaje": round(sum(desglose.values()), 2),
        "desglose": desglose,
    }


def destinos_de_expansion(
    tablero: dict,
    propios: list[frozenset],
    rivales: list[frozenset],
    max_caminos: int = 3,
    cuantos: int = 3,
) -> list[dict]:
    """
    Los mejores vértices para tu siguiente poblado, de mayor a menor puntaje.

    Parameters
    ----------
    tablero : dict
        El tablero del dominio.
    propios, rivales : list of frozenset
        Los poblados ya colocados.
    max_caminos : int
        Hasta cuántos caminos de distancia se buscan destinos.
    cuantos : int
        Cuántos destinos devolver.
    """
    poblados = [*propios, *rivales]
    rutas = rutas_desde(propios, rivales, max_caminos)
    candidatos = [
        puntuar_destino(v, ruta, propios, rivales, tablero)
        for v, ruta in rutas.items()
        if len(ruta) - 1 >= CAMINOS_MINIMOS and es_legal(v, poblados)
    ]
    # Empates: gana el más cercano, que se construye antes.
    candidatos.sort(key=lambda d: (-d["puntaje"], d["caminos"]))
    return candidatos[:cuantos]


def verificar_expansion(destinos: list[dict], propios, rivales) -> None:
    """Cada destino es legal, su ruta sale de un poblado propio y no cruza rivales."""
    poblados = [*propios, *rivales]
    for d in destinos:
        assert es_legal(d["vertice"], poblados), "Destino junto a un poblado"
        assert d["ruta"][0] in propios, "La ruta no sale de un poblado propio"
        assert not set(d["ruta"]) & set(rivales), "La ruta cruza un poblado rival"
        assert d["caminos"] == len(d["ruta"]) - 1 >= CAMINOS_MINIMOS
        for a, b in zip(d["ruta"], d["ruta"][1:], strict=False):
            assert b in TOPOLOGIA.adyacentes[a], "La ruta salta una arista"
