"""
variables.py
============
Ingeniería de variables sobre PAREJAS de vértices.

Por qué parejas y no vértices sueltos
-------------------------------------
La colocación inicial de Catan reparte dos poblados por jugador, así que la
decisión real es de pareja. Y midiéndolo se ve por qué importa: un vértice suelto
tiene madera y ladrillo a la vez en apenas el 9% de los casos, porque toca tres
hexágonos como máximo. Una pareja toca hasta seis, y ahí las combinaciones
completas dejan de ser raras.

Regla que gobierna este módulo
------------------------------
Una variable solo sirve si VARÍA entre las parejas candidatas del mismo tablero.
Una cantidad que valga igual para todas (el total de pips del tablero, su
promedio) no puede explicar por qué una pareja es mejor que otra.
`verificar_variabilidad()` lo comprueba automáticamente.
"""

from __future__ import annotations

from collections import deque

from app.domain.tablero import (
    COSTOS,
    RECURSOS,
    generar_tablero,
    hexagonos_del_vertice,
    pips_del_vertice,
    puerto_del_vertice,
    todos_los_vertices,
    vertices_adyacentes,
)

#: Tope de rondas para las variables de tiempo. Mayor que una partida completa,
#: así que significa "no llegas".
TOPE_TURNOS = 60.0

#: Radio, en aristas, al medir el espacio disponible para tender caminos.
RADIO_CAMINOS = 3


# ---------------------------------------------------------------------------
# Topología precalculada (idéntica para todos los tableros)
# ---------------------------------------------------------------------------

_VERTICES = todos_los_vertices()
_ADYACENTES = {v: vertices_adyacentes(v, _VERTICES) for v in _VERTICES}


def _distancias_desde(origen: frozenset) -> dict:
    """Distancia en aristas desde un vértice a todos los demás."""
    distancia = {origen: 0}
    cola = deque([origen])
    while cola:
        actual = cola.popleft()
        for vecino in _ADYACENTES[actual]:
            if vecino not in distancia:
                distancia[vecino] = distancia[actual] + 1
                cola.append(vecino)
    return distancia


#: Distancias entre todos los pares de vértices. Se calcula una sola vez.
_DISTANCIAS = {v: _distancias_desde(v) for v in _VERTICES}


def _aristas_cercanas(vertice: frozenset, saltos: int = RADIO_CAMINOS) -> int:
    """
    Cuántas aristas hay dentro de un radio de `saltos` alrededor del vértice.

    Mide el espacio disponible para tender caminos. La carta de camino más largo
    exige cinco caminos conectados, y un vértice acorralado contra la costa tiene
    menos aristas alrededor que uno del centro.

    No se mide la cadena más larga posible porque, en un tablero vacío, desde
    cualquier vértice se encadenan seis o más aristas bordeando la costa: esa
    medida resulta constante y no distingue nada.
    """
    visitados = {vertice}
    frontera = [vertice]
    aristas = set()
    for _ in range(saltos):
        siguiente = []
        for v in frontera:
            for vecino in _ADYACENTES[v]:
                aristas.add(frozenset({v, vecino}))
                if vecino not in visitados:
                    visitados.add(vecino)
                    siguiente.append(vecino)
        frontera = siguiente
    return len(aristas)


#: El espacio de caminos solo depende de la geometría, no del tablero.
_ARISTAS_CERCANAS = {v: _aristas_cercanas(v) for v in _VERTICES}


# ---------------------------------------------------------------------------
# Cantidades auxiliares
# ---------------------------------------------------------------------------

def _pips_por_recurso(vertice: frozenset, tablero: dict) -> dict[str, int]:
    """Pips que aporta cada recurso a un vértice."""
    salida = {r: 0 for r in RECURSOS}
    for h in hexagonos_del_vertice(vertice, tablero):
        recurso = tablero["recursos"][h]
        if recurso is not None:
            salida[recurso] += tablero["pips"][h]
    return salida


def pips_por_recurso_del_tablero(tablero: dict) -> dict[str, int]:
    """Pips totales de cada recurso en todo el tablero. Igual para toda pareja."""
    salida = {r: 0 for r in RECURSOS}
    for h in tablero["hexagonos"]:
        recurso = tablero["recursos"][h]
        if recurso is not None:
            salida[recurso] += tablero["pips"][h]
    return salida


def _tasa_de_cambio(recurso: str | None, puertos: set[str]) -> int:
    """Cuántas cartas del recurso cuestan una carta cualquiera."""
    if recurso is not None and recurso in puertos:
        return 2
    if "3:1" in puertos:
        return 3
    return 4


# ---------------------------------------------------------------------------
# Variables de una pareja
# ---------------------------------------------------------------------------

def variables_de_pareja(
    v1: frozenset,
    v2: frozenset,
    tablero: dict,
    jugadores: int = 4,
    pips_tablero: dict[str, int] | None = None,
) -> dict[str, float]:
    """
    Calcula todas las variables de una pareja de vértices.

    Parameters
    ----------
    v1, v2 : frozenset
        Los dos vértices donde se colocan los poblados iniciales.
    tablero : dict
        Tablero devuelto por ``tablero.generar_tablero``.
    jugadores : int
        Cuántos juegan la partida. Influye en dos cosas: con más gente hay más
        tiradas por ronda, así que se cobra más seguido, y hay más poblados en
        el tablero, así que queda menos espacio para expandirse.
    pips_tablero : dict, opcional
        Pips por recurso del tablero. Al procesar muchas parejas del mismo
        tablero conviene calcularlo una vez y reutilizarlo.

    Returns
    -------
    dict
        Nombre de variable -> valor numérico.
    """
    if pips_tablero is None:
        pips_tablero = pips_por_recurso_del_tablero(tablero)

    hex1 = hexagonos_del_vertice(v1, tablero)
    hex2 = hexagonos_del_vertice(v2, tablero)
    pr1 = _pips_por_recurso(v1, tablero)
    pr2 = _pips_por_recurso(v2, tablero)

    # Los dos poblados producen por separado: si ambos tocan el mismo hexágono,
    # al salir su número se cobran dos cartas. Por eso se suma con repetición.
    pr = {r: pr1[r] + pr2[r] for r in RECURSOS}
    pips_totales = sum(pr.values())

    puertos = {
        p for p in (puerto_del_vertice(v1, tablero), puerto_del_vertice(v2, tablero))
        if p is not None
    }

    v: dict[str, float] = {}

    # -- Fase 1: directas ---------------------------------------------------
    v["pips_totales"] = float(pips_totales)
    v["num_hexagonos"] = float(len(hex1) + len(hex2))
    v["hexagonos_distintos"] = float(len(set(hex1) | set(hex2)))
    v["num_recursos_distintos"] = float(sum(1 for p in pr.values() if p > 0))
    for recurso in RECURSOS:
        v[f"pips_{recurso}"] = float(pr[recurso])
    v["toca_desierto"] = float(
        any(tablero["terrenos"][h] == "desierto" for h in hex1 + hex2)
    )
    v["num_puertos"] = float(len(puertos))
    v["puerto_generico"] = float("3:1" in puertos)
    v["puerto_especifico"] = float(any(p != "3:1" for p in puertos))
    v["jugadores"] = float(jugadores)

    # -- Fase 2: combinaciones que completan construcciones -----------------
    # Se usa el mínimo porque construir exige AMBOS recursos: con 8 pips de
    # madera y 1 de ladrillo construyes al ritmo del ladrillo.
    v["par_camino"] = float(min(pr["madera"], pr["ladrillo"]))
    v["par_ciudad"] = min(pr["trigo"] / 2.0, pr["mineral"] / 3.0)
    v["trio_desarrollo"] = float(min(pr["trigo"], pr["oveja"], pr["mineral"]))
    # El poblado cuesta cuatro recursos. Un vértice suelto nunca los tiene todos
    # porque toca tres hexágonos; una pareja sí puede. Por eso esta variable
    # solo existe a nivel de pareja.
    v["cuarteto_poblado"] = float(
        min(pr["madera"], pr["ladrillo"], pr["trigo"], pr["oveja"])
    )

    # -- Fase 2: control del suministro del tablero --------------------------
    # No se usa "cuánta madera hay en el tablero": es igual para todas las
    # parejas. Lo que varía es qué fracción de ese suministro controlas.
    # Puede pasar de 1: si los dos poblados tocan el mismo hexágono, cobras dos
    # cartas cada vez que sale su número, así que recibes más de lo que el
    # tablero contiene contando una sola vez.
    controles = []
    for recurso in RECURSOS:
        total = pips_tablero[recurso]
        control = pr[recurso] / total if total > 0 else 0.0
        v[f"control_{recurso}"] = control
        controles.append(control)
    v["control_suministro"] = float(sum(controles))
    v["control_maximo"] = float(max(controles))

    # -- Fase 2: forma de la producción -------------------------------------
    v["desequilibrio"] = max(pr.values()) / pips_totales if pips_totales > 0 else 0.0
    dominante = max(RECURSOS, key=lambda r: pr[r]) if pips_totales > 0 else None
    # Un puerto 2:1 solo vale de verdad si es del recurso que te sobra: ahí
    # tienes casi un monopolio y conviertes a mitad de precio.
    v["puerto_alineado"] = float(
        dominante is not None and dominante in puertos and pr[dominante] > 0
    )

    # -- Fase 3: producción efectiva ----------------------------------------
    # Un recurso que sobra no se pierde, pero se cambia a un precio. El excedente
    # sobre un reparto parejo se divide entre su tasa de cambio.
    equilibrio = pips_totales / 5.0
    efectiva = 0.0
    for recurso in RECURSOS:
        tasa = _tasa_de_cambio(recurso, puertos)
        efectiva += min(pr[recurso], equilibrio) + max(0.0, pr[recurso] - equilibrio) / tasa
    v["produccion_efectiva"] = efectiva

    # -- Fase 3: turnos estimados hasta cada construcción --------------------
    # Un recurso que no produces NO te bloquea: lo compras en el banco. Sin
    # contemplar el comercio, casi todas las parejas topaban en TOPE_TURNOS y la
    # variable no distinguía nada.
    cartas_por_ronda = {r: pr[r] / 36.0 * jugadores for r in RECURSOS}
    ritmo_mayor = max(cartas_por_ronda.values())
    tasa_dominante = _tasa_de_cambio(dominante, puertos)

    for nombre, costo in COSTOS.items():
        turnos = 0.0
        for recurso, cantidad in costo.items():
            ritmo = cartas_por_ronda[recurso]
            if ritmo > 0:
                espera = cantidad / ritmo
            elif ritmo_mayor > 0:
                espera = cantidad * tasa_dominante / ritmo_mayor
            else:
                espera = TOPE_TURNOS
            turnos = max(turnos, espera)
        v[f"turnos_a_{nombre}"] = min(turnos, TOPE_TURNOS)

    # -- Fase 3: espacio de expansión ---------------------------------------
    # Los vecinos inmediatos de un poblado nunca son legales: la regla de
    # distancia mínima lo prohíbe. Por eso se mide desde distancia 2.
    ocupados = {v1, v2}
    bloqueados = set(ocupados)
    for ocupado in ocupados:
        bloqueados.update(_ADYACENTES[ocupado])

    libres_2, libres_3 = set(), set()
    for origen in ocupados:
        for candidato, distancia in _DISTANCIAS[origen].items():
            if candidato in bloqueados:
                continue
            if distancia == 2:
                libres_2.add(candidato)
            elif distancia == 3:
                libres_3.add(candidato)
    libres_3 -= libres_2

    v["vertices_expansion_2"] = float(len(libres_2))
    v["vertices_expansion_3"] = float(len(libres_3))
    cercanos = libres_2 | libres_3
    pips_cercanos = [pips_del_vertice(c, tablero) for c in cercanos]
    v["pips_vecinos_max"] = float(max(pips_cercanos)) if pips_cercanos else 0.0
    v["pips_vecinos_media"] = (
        sum(pips_cercanos) / len(pips_cercanos) if pips_cercanos else 0.0
    )
    v["aristas_cercanas"] = float(_ARISTAS_CERCANAS[v1] + _ARISTAS_CERCANAS[v2])

    # -- Variables que solo existen a nivel de pareja ------------------------
    # Si los dos poblados comparten hexágono, concentras la producción en pocos
    # números en vez de diversificar. Suele ser malo.
    v["solapamiento"] = float(len(set(hex1) & set(hex2)))

    # Qué tan separados están. Influye en si sus redes de caminos llegan a unirse,
    # que es lo que hace viable la carta de camino más largo.
    v["distancia"] = float(_DISTANCIAS[v1].get(v2, 0))

    # Cuántos recursos aporta la pareja que ninguno de los dos tenía por su
    # cuenta. Es la medida directa de que se complementen.
    distintos_1 = sum(1 for p in pr1.values() if p > 0)
    distintos_2 = sum(1 for p in pr2.values() if p > 0)
    v["complementariedad"] = float(
        v["num_recursos_distintos"] - max(distintos_1, distintos_2)
    )

    return v


# ---------------------------------------------------------------------------
# Aplicación a un tablero completo
# ---------------------------------------------------------------------------

def variables_de_parejas(
    tablero: dict,
    parejas: list[tuple],
    jugadores: int = 4,
) -> list[dict]:
    """
    Calcula las variables de una lista de parejas del mismo tablero.

    Returns
    -------
    list of dict
        Una fila por pareja, con ``pareja_id`` para poder rastrearla.
    """
    pips_tablero = pips_por_recurso_del_tablero(tablero)
    filas = []
    for v1, v2 in parejas:
        fila = {"pareja_id": identificador(v1, v2)}
        fila.update(variables_de_pareja(v1, v2, tablero, jugadores, pips_tablero))
        filas.append(fila)
    return filas


def identificador(v1: frozenset, v2: frozenset) -> str:
    """Texto estable que identifica una pareja, independiente del orden."""
    def texto(v):
        return "|".join(f"({q},{r})" for q, r in sorted(v))
    return " + ".join(sorted([texto(v1), texto(v2)]))


def nombres_de_variables() -> list[str]:
    """Los nombres de las variables, en orden, sin incluir ``pareja_id``."""
    tablero = generar_tablero(semilla=0)
    return list(variables_de_pareja(_VERTICES[0], _VERTICES[30], tablero).keys())


# ---------------------------------------------------------------------------
# Verificación
# ---------------------------------------------------------------------------

def verificar_variables(tablero: dict, parejas: list[tuple], jugadores: int = 4) -> None:
    """Lanza AssertionError si alguna variable está mal construida."""
    filas = variables_de_parejas(tablero, parejas, jugadores)
    assert filas, "No se recibió ninguna pareja"

    llaves = set(filas[0]) - {"pareja_id"}
    for fila in filas:
        assert set(fila) - {"pareja_id"} == llaves, "Las parejas no comparten variables"

    for fila, (v1, v2) in zip(filas, parejas):
        for nombre, valor in fila.items():
            if nombre == "pareja_id":
                continue
            assert valor is not None, f"{nombre} es None"
            assert valor == valor, f"{nombre} es NaN"
            assert abs(valor) != float("inf"), f"{nombre} es infinito"

        pips = pips_del_vertice(v1, tablero) + pips_del_vertice(v2, tablero)
        assert fila["pips_totales"] == pips, "pips_totales no coincide con tablero.py"
        assert sum(fila[f"pips_{r}"] for r in RECURSOS) == pips, (
            "Los pips por recurso no suman el total"
        )
        assert fila["produccion_efectiva"] <= fila["pips_totales"] + 1e-9, (
            "La producción efectiva no puede superar los pips totales"
        )
        assert fila["par_camino"] <= min(fila["pips_madera"], fila["pips_ladrillo"]) + 1e-9
        assert fila["distancia"] >= 2, (
            "Dos poblados no pueden estar a distancia menor que 2"
        )
        for r in RECURSOS:
            # El tope es 2 y no 1: con los dos poblados sobre el mismo hexágono
            # se cobra doble (ver el comentario en variables_de_pareja).
            assert 0.0 <= fila[f"control_{r}"] <= 2.0, f"control_{r} fuera de [0, 2]"


def variables_constantes(filas: list[dict]) -> list[str]:
    """Variables que valen lo mismo en todas las filas recibidas."""
    llaves = set(filas[0]) - {"pareja_id"}
    return sorted(n for n in llaves if len({f[n] for f in filas}) == 1)


def verificar_variabilidad(tableros: int = 20) -> None:
    """
    Comprueba que ninguna variable sea constante a lo largo de varios tableros.

    Una variable que nunca cambia no puede explicar por qué una pareja es mejor
    que otra, así que sobra. Esta comprobación caza el error más común de la
    ingeniería de variables de este proyecto.
    """
    from app.domain.simulador import parejas_candidatas

    filas = []
    for semilla in range(tableros):
        tablero = generar_tablero(semilla=semilla)
        parejas = parejas_candidatas(tablero, top=10)
        jugadores = 3 if semilla % 2 else 4
        filas.extend(variables_de_parejas(tablero, parejas, jugadores))

    constantes = variables_constantes(filas)
    assert not constantes, (
        f"Variables constantes en {tableros} tableros, no sirven para rankear: "
        f"{constantes}"
    )


if __name__ == "__main__":
    from app.domain.simulador import parejas_candidatas

    tablero = generar_tablero(semilla=42)
    parejas = parejas_candidatas(tablero, top=15)
    filas = variables_de_parejas(tablero, parejas, jugadores=4)
    nombres = [n for n in filas[0] if n != "pareja_id"]

    print(f"{len(nombres)} variables para {len(filas)} parejas candidatas:\n")
    for i in range(0, len(nombres), 3):
        print("  " + "".join(n.ljust(26) for n in nombres[i:i + 3]))

    verificar_variables(tablero, parejas)
    verificar_variabilidad(tableros=20)
    print("\nverificar_variables() y verificar_variabilidad(): todo en orden.")

    escasas = variables_constantes(filas)
    if escasas:
        print(f"Constantes en ESTE tablero (no es error, son escasas): {escasas}")

    mejores = sorted(filas, key=lambda f: f["pips_totales"], reverse=True)[:6]
    print("\nLas 6 parejas con más pips del tablero de la semilla 42:\n")
    cab = (f"{'pips':>5} {'par_cam':>8} {'cuarteto':>9} {'prod_ef':>8} "
           f"{'complem':>8} {'solape':>7} {'dist':>5}")
    print(cab)
    print("-" * len(cab))
    for f in mejores:
        print(
            f"{f['pips_totales']:5.0f} {f['par_camino']:8.1f} "
            f"{f['cuarteto_poblado']:9.1f} {f['produccion_efectiva']:8.2f} "
            f"{f['complementariedad']:8.0f} {f['solapamiento']:7.0f} "
            f"{f['distancia']:5.0f}"
        )
