"""
simulador.py
============
Mini-partida en solitario para medir el valor real de un vértice.

Por qué existe
--------------
La producción esperada de recursos de un vértice se calcula con una fórmula
exacta (pips / 36), así que no hay nada que aprender ahí. Lo que sí es difícil
de predecir es hasta dónde llegas con esos recursos, porque construir cuesta
combinaciones exactas, los dados caen en enteros y cambiar en el banco tiene un
precio.

Este módulo mide justamente eso: coloca un poblado en un vértice, juega N turnos
tirando dados y construyendo lo que alcance, y devuelve los puntos de victoria
conseguidos. Esa cifra, promediada sobre muchas partidas, es la variable
objetivo del modelo.

Simplificaciones declaradas
---------------------------
- Un solo jugador: no hay rivales que bloqueen vértices ni que compitan por la
  carta de camino más largo o el ejército mayor.
- El ladrón solo se modela por su efecto de descarte al salir el 7.
- No hay intercambio entre jugadores, solo con el banco y los puertos.
- La política de construcción es fija y codiciosa, no óptima.

Estas simplificaciones son aceptables porque el objetivo no es simular Catan con
fidelidad, sino producir una medida comparable entre vértices del mismo tablero.
"""

from __future__ import annotations

import random
from collections import deque

from app.domain.tablero import (
    COSTOS,
    RECURSOS,
    generar_tablero,
    hexagonos_del_vertice,
    pips_del_vertice,
    puerto_del_vertice,
    todas_las_aristas,
    todos_los_vertices,
    vertices_adyacentes,
)

# ---------------------------------------------------------------------------
# Parámetros de la simulación
# ---------------------------------------------------------------------------

RONDAS = 20                  # rondas de mesa; deja la escala de puntos en el rango
                             # real de Catan, de 0 a unos 10 puntos
JUGADORES = 4                # cuántos tiran los dados en cada ronda
CABALLEROS_EJERCITO = 3      # caballeros necesarios para el ejército mayor
CAMINOS_RUTA_LARGA = 5       # caminos necesarios para la carta de camino más largo
LIMITE_MANO = 7              # cartas por encima de las cuales el 7 obliga a descartar

#: Composición del mazo de desarrollo del juego base (25 cartas).
MAZO_DESARROLLO = ["caballero"] * 14 + ["punto"] * 5 + ["progreso"] * 6


# ---------------------------------------------------------------------------
# Estructura auxiliar: la topología precalculada
# ---------------------------------------------------------------------------

class Topologia:
    """
    Guarda la geometría del tablero, que es la misma para todos los tableros.

    Calcularla una sola vez y reutilizarla es lo que hace viable correr cientos
    de miles de simulaciones.
    """

    def __init__(self):
        self.vertices = todos_los_vertices()
        self.aristas = todas_las_aristas()
        self.adyacentes = {
            v: vertices_adyacentes(v, self.vertices) for v in self.vertices
        }
        self.aristas_de_vertice = {v: [] for v in self.vertices}
        for arista in self.aristas:
            for v in arista:
                self.aristas_de_vertice[v].append(arista)


TOPOLOGIA = Topologia()


# ---------------------------------------------------------------------------
# Estado de una partida
# ---------------------------------------------------------------------------

class Partida:
    """Una mini-partida en solitario desde un vértice inicial."""

    def __init__(self, tablero: dict, colocacion: tuple, rng: random.Random):
        """
        Parameters
        ----------
        colocacion : tuple de frozenset
            Los vértices donde arranca el jugador. En Catan son dos, porque la
            colocación inicial reparte dos poblados por jugador.
        """
        self.tablero = tablero
        self.rng = rng
        self.topo = TOPOLOGIA

        self.recursos = {r: 0 for r in RECURSOS}
        self.poblados = set(colocacion)
        self.ciudades = set()
        self.caminos = set()
        self.caballeros = 0
        self.puntos_por_cartas = 0

        # Cada poblado inicial viene con su camino, como en la colocación real.
        for vertice in colocacion:
            self.caminos.add(self.topo.aristas_de_vertice[vertice][0])

        # Qué hexágonos producen para mí, y con qué multiplicador.
        self.produccion = {}
        self._recalcular_produccion()

    # -- producción -------------------------------------------------------

    def _recalcular_produccion(self):
        """Mapa numero_de_dado -> lista de (recurso, cantidad)."""
        self.produccion = {}
        ocupados = [(v, 1) for v in self.poblados] + [(v, 2) for v in self.ciudades]
        for vertice, multiplicador in ocupados:
            for h in hexagonos_del_vertice(vertice, self.tablero):
                recurso = self.tablero["recursos"][h]
                if recurso is None:
                    continue
                numero = self.tablero["numeros"][h]
                self.produccion.setdefault(numero, []).append((recurso, multiplicador))

    def cobrar(self, numero: int):
        for recurso, cantidad in self.produccion.get(numero, []):
            self.recursos[recurso] += cantidad

    # -- comercio ---------------------------------------------------------

    def _puertos_propios(self) -> set[str]:
        tipos = set()
        for v in self.poblados | self.ciudades:
            p = puerto_del_vertice(v, self.tablero)
            if p is not None:
                tipos.add(p)
        return tipos

    def tasa_de_cambio(self, recurso: str) -> int:
        """Cuántas cartas de ese recurso cuestan una carta cualquiera."""
        puertos = self._puertos_propios()
        if recurso in puertos:
            return 2
        if "3:1" in puertos:
            return 3
        return 4

    def intentar_cambio(self, falta: str) -> bool:
        """Cambia el excedente más barato por el recurso que falta."""
        mejor, mejor_tasa = None, None
        for recurso, cantidad in self.recursos.items():
            if recurso == falta:
                continue
            tasa = self.tasa_de_cambio(recurso)
            if cantidad >= tasa and (mejor_tasa is None or tasa < mejor_tasa):
                mejor, mejor_tasa = recurso, tasa
        if mejor is None:
            return False
        self.recursos[mejor] -= mejor_tasa
        self.recursos[falta] += 1
        return True

    # -- construcción -----------------------------------------------------

    def puede_pagar(self, construccion: str) -> bool:
        return all(self.recursos[r] >= n for r, n in COSTOS[construccion].items())

    def pagar(self, construccion: str):
        for r, n in COSTOS[construccion].items():
            self.recursos[r] -= n

    def _mis_vertices(self) -> set:
        """Vértices que toco con poblados, ciudades o caminos."""
        alcance = set(self.poblados) | set(self.ciudades)
        for arista in self.caminos:
            alcance |= set(arista)
        return alcance

    def vertices_libres(self) -> list:
        """Dónde podría poner un poblado ahora: conectado y a distancia legal."""
        ocupados = self.poblados | self.ciudades
        libres = []
        for v in self._mis_vertices():
            if v in ocupados:
                continue
            if any(vecino in ocupados for vecino in self.topo.adyacentes[v]):
                continue
            libres.append(v)
        return libres

    def _objetivo_de_expansion(self) -> frozenset | None:
        """El mejor vértice al que vale la pena tender caminos."""
        ocupados = self.poblados | self.ciudades
        candidatos = [
            v for v in self.topo.vertices
            if v not in ocupados
            and not any(vecino in ocupados for vecino in self.topo.adyacentes[v])
            and pips_del_vertice(v, self.tablero) > 0
        ]
        if not candidatos:
            return None
        return max(candidatos, key=lambda v: pips_del_vertice(v, self.tablero))

    def _siguiente_camino(self) -> frozenset | None:
        """
        La arista que acerca mi red al mejor vértice disponible.

        Busca en anchura desde mi red hasta el objetivo y devuelve el primer
        tramo del camino más corto.
        """
        objetivo = self._objetivo_de_expansion()
        if objetivo is None:
            return None

        origen = self._mis_vertices()
        if objetivo in origen:
            return None

        # Anchura desde mi red hasta el objetivo, guardando por dónde se llegó.
        previo = {v: None for v in origen}
        cola = deque(origen)
        while cola:
            actual = cola.popleft()
            if actual == objetivo:
                break
            for vecino in self.topo.adyacentes[actual]:
                if vecino not in previo:
                    previo[vecino] = actual
                    cola.append(vecino)
        if objetivo not in previo:
            return None

        # Reconstruye la ruta y devuelve su primer tramo que aún no tengo.
        ruta, nodo = [], objetivo
        while previo[nodo] is not None:
            ruta.append(frozenset({previo[nodo], nodo}))
            nodo = previo[nodo]
        for arista in reversed(ruta):
            if arista not in self.caminos:
                return arista
        return None

    def _ruta_mas_larga(self) -> int:
        """Longitud del camino continuo más largo de mi red."""
        if not self.caminos:
            return 0
        vecinos = {}
        for arista in self.caminos:
            a, b = tuple(arista)
            vecinos.setdefault(a, []).append(b)
            vecinos.setdefault(b, []).append(a)

        mejor = 0

        def explorar(actual, usadas):
            nonlocal mejor
            mejor = max(mejor, len(usadas))
            for siguiente in vecinos[actual]:
                arista = frozenset({actual, siguiente})
                if arista not in usadas:
                    explorar(siguiente, usadas | {arista})

        for inicio in vecinos:
            explorar(inicio, frozenset())
        return mejor

    # -- turno ------------------------------------------------------------

    def construir(self):
        """
        Política de construcción, en orden de prioridad.

        Ciudad primero porque duplica producción y da un punto extra; luego
        poblado, que es un punto y más producción; luego camino, que abre
        espacio; y al final carta de desarrollo con el excedente.
        """
        for _ in range(4):  # como mucho cuatro construcciones por turno
            if self.ciudades or self.poblados:
                if self.puede_pagar("ciudad") and self.poblados:
                    objetivo = max(
                        self.poblados,
                        key=lambda v: pips_del_vertice(v, self.tablero),
                    )
                    self.pagar("ciudad")
                    self.poblados.remove(objetivo)
                    self.ciudades.add(objetivo)
                    self._recalcular_produccion()
                    continue

            libres = self.vertices_libres()
            if self.puede_pagar("poblado") and libres:
                objetivo = max(libres, key=lambda v: pips_del_vertice(v, self.tablero))
                self.pagar("poblado")
                self.poblados.add(objetivo)
                self._recalcular_produccion()
                continue

            if self.puede_pagar("camino"):
                arista = self._siguiente_camino()
                if arista is not None:
                    self.pagar("camino")
                    self.caminos.add(arista)
                    continue

            if self.puede_pagar("carta_desarrollo"):
                self.pagar("carta_desarrollo")
                carta = self.rng.choice(MAZO_DESARROLLO)
                if carta == "caballero":
                    self.caballeros += 1
                elif carta == "punto":
                    self.puntos_por_cartas += 1
                continue

            break

    def cambiar_si_conviene(self):
        """Si no puedo construir nada pero me sobra algo, cambio en el banco."""
        if self.puede_pagar("ciudad") or self.puede_pagar("poblado"):
            return
        objetivo = "ciudad" if self.ciudades or len(self.poblados) > 1 else "poblado"
        for recurso, necesarios in COSTOS[objetivo].items():
            if self.recursos[recurso] < necesarios:
                self.intentar_cambio(recurso)
                return

    def descartar_por_ladron(self):
        total = sum(self.recursos.values())
        if total <= LIMITE_MANO:
            return
        a_descartar = total // 2
        bolsa = [r for r, n in self.recursos.items() for _ in range(n)]
        self.rng.shuffle(bolsa)
        for r in bolsa[:a_descartar]:
            self.recursos[r] -= 1

    def jugar_ronda(self, jugadores: int = 4):
        """
        Una ronda completa de la mesa.

        En Catan se cobra en CADA tirada de la partida, no solo en la propia:
        si sale tu número mientras juega otro, igual recibes la carta. Con cuatro
        jugadores eso significa cuatro tiradas por ronda. Construir, en cambio,
        solo se puede en el turno propio.
        """
        for _ in range(jugadores):
            dado = self.rng.randint(1, 6) + self.rng.randint(1, 6)
            if dado == 7:
                self.descartar_por_ladron()
            else:
                self.cobrar(dado)
        self.construir()
        self.cambiar_si_conviene()

    # -- resultado --------------------------------------------------------

    def puntos(self) -> int:
        total = len(self.poblados) + 2 * len(self.ciudades) + self.puntos_por_cartas
        if self.caballeros >= CABALLEROS_EJERCITO:
            total += 2
        if self._ruta_mas_larga() >= CAMINOS_RUTA_LARGA:
            total += 2
        return total


# ---------------------------------------------------------------------------
# Interfaz pública
# ---------------------------------------------------------------------------

def simular_colocacion(
    tablero: dict,
    colocacion: tuple,
    partidas: int = 60,
    rondas: int = RONDAS,
    jugadores: int = JUGADORES,
    semilla: int | None = None,
) -> float:
    """
    Puntos de victoria promedio al empezar con esta colocación.

    Parameters
    ----------
    tablero : dict
        El tablero devuelto por ``generar_tablero``.
    colocacion : tuple de frozenset
        Los vértices iniciales. Normalmente dos, que es lo que reparte la
        colocación inicial de Catan.
    partidas : int
        Cuántas mini-partidas promediar. Más partidas, menos ruido.
    rondas : int
        Rondas de mesa por partida.
    jugadores : int
        Cuántos tiran los dados en cada ronda. Con más jugadores hay más tiradas,
        así que se cobra más seguido.
    semilla : int, opcional
        Fija el azar para que el resultado sea reproducible.

    Returns
    -------
    float
        Promedio de puntos de victoria. Es la variable objetivo del modelo.
    """
    rng = random.Random(semilla)
    acumulado = 0
    for _ in range(partidas):
        partida = Partida(tablero, colocacion, rng)
        for _ in range(rondas):
            partida.jugar_ronda(jugadores)
        acumulado += partida.puntos()
    return acumulado / partidas


def simular_pareja(tablero, v1, v2, **kwargs) -> float:
    """Atajo para la colocación de dos poblados, que es el caso normal."""
    return simular_colocacion(tablero, (v1, v2), **kwargs)


def parejas_candidatas(
    tablero: dict,
    ocupados: set | None = None,
    top: int = 15,
    con_puerto: int = 6,
    obligatorio: frozenset | None = None,
) -> list[tuple]:
    """
    Parejas de vértices que vale la pena evaluar.

    Puntuar las 1431 parejas posibles sería lento e inútil: casi todas son malas.
    Se preselecciona y se forman las parejas legales entre las preseleccionadas.

    La preselección NO puede ser solo por pips. Los puertos están en la costa, y
    los vértices costeros tocan uno o dos hexágonos en vez de tres, así que
    siempre quedan por debajo en pips. Al elegir solo por pips desaparecían todos
    los vértices con puerto, y con ellos la jugada de concentrar un recurso y
    cambiarlo 2:1, que es una estrategia real del juego. Por eso se añaden los
    mejores vértices con puerto aunque no entren por pips.

    Parameters
    ----------
    top : int
        Cuántos vértices tomar por pips.
    con_puerto : int
        Cuántos vértices con puerto añadir, los de más pips entre ellos.
    ocupados : set, opcional
        Vértices ya tomados por otros jugadores. Sus vecinos quedan bloqueados
        por la regla de distancia mínima de dos.
    obligatorio : frozenset, opcional
        Un vértice que ya es del jugador. Si se pasa, todas las parejas lo
        incluyen: sirve para la segunda colocación, cuando el primer poblado ya
        está puesto y solo falta elegir el que mejor lo complemente.
    """
    ocupados = ocupados or set()
    bloqueados = set(ocupados)
    for v in ocupados:
        bloqueados.update(TOPOLOGIA.adyacentes[v])

    libres = [v for v in TOPOLOGIA.vertices if v not in bloqueados]
    libres.sort(key=lambda v: pips_del_vertice(v, tablero), reverse=True)

    seleccion = list(libres[:top])
    portuarios = [
        v for v in libres
        if v not in seleccion and puerto_del_vertice(v, tablero) is not None
    ]
    seleccion.extend(portuarios[:con_puerto])

    if obligatorio is not None:
        # Segunda colocación: el primer poblado ya está, solo se busca compañero.
        return [
            (obligatorio, b) for b in libres
            if b != obligatorio and b not in TOPOLOGIA.adyacentes[obligatorio]
        ]

    parejas = []
    for i, a in enumerate(seleccion):
        for b in seleccion[i + 1:]:
            # Dos poblados propios tampoco pueden ser adyacentes entre sí.
            if b not in TOPOLOGIA.adyacentes[a]:
                parejas.append((a, b))
    return parejas


if __name__ == "__main__":
    import time

    tablero = generar_tablero(semilla=42)
    parejas = parejas_candidatas(tablero, top=15)

    inicio = time.perf_counter()
    resultados = [
        (a, b, simular_pareja(tablero, a, b, partidas=40, semilla=1))
        for a, b in parejas
    ]
    duracion = time.perf_counter() - inicio
    resultados.sort(key=lambda x: x[2], reverse=True)

    print(f"{len(parejas)} parejas candidatas simuladas en {duracion:.1f} s\n")

    def describir(v):
        hs = hexagonos_del_vertice(v, tablero)
        return ", ".join(
            f"{tablero['recursos'][h] or 'desierto'}-{tablero['numeros'].get(h, 'x')}"
            for h in hs
        )

    print("Las 3 mejores parejas:\n")
    for a, b, puntos in resultados[:3]:
        pips = pips_del_vertice(a, tablero) + pips_del_vertice(b, tablero)
        print(f"  {puntos:.2f} puntos | {pips} pips")
        print(f"     A: {describir(a)}")
        print(f"     B: {describir(b)}\n")

    print("La peor de las candidatas:\n")
    a, b, puntos = resultados[-1]
    pips = pips_del_vertice(a, tablero) + pips_del_vertice(b, tablero)
    print(f"  {puntos:.2f} puntos | {pips} pips")
    print(f"     A: {describir(a)}")
    print(f"     B: {describir(b)}")
