"""
Lectura del tablero a partir de una fotografía.

Estrategia
----------
El tablero de Catan tiene topología **fija**: 19 hexágonos en filas 3-4-5-4-3.
Eso permite evitar la detección abierta de objetos:

1. **Fichas → red.** Las fichas numéricas son discos crema y cada una marca el
   centro de su hexágono. Con unas pocas se ajusta la red hexagonal y una
   homografía del plano canónico a la foto (``services/vision_fichas.py``). Así
   no importa el fondo ni la perspectiva.
2. **Terrenos.** Se clasifica por color un anillo entre la ficha y el borde de
   cada pieza. El desierto es el único hexágono sin ficha.
3. **Números.** Se leen por rasgos que no dependen de la tipografía (rojo,
   dígitos, agujeros, pips) y respetando el reparto del juego base.
4. **Respaldo.** Si no se encuentran fichas, se endereza la foto por el borde del
   tablero (el método anterior, menos fiable) y se avisa.

El resultado nunca se da por definitivo: cada hexágono viaja con la confianza de su
terreno y de su número, y la interfaz pide revisar lo dudoso antes de calcular.

La imagen solo se procesa en memoria: no se guarda en disco ni en ningún registro.
"""

from __future__ import annotations

from collections import Counter

import cv2
import numpy as np

from app.domain.puertos import plantilla_de_puertos
from app.domain.tablero import TERRENOS, coordenadas_hexagonos
from app.schemas.api import HexagonoDetectado, RespuestaVision, Tablero
from app.services import vision_fichas as fichas
from app.services.serializers import (
    avisos_del_tablero,
    id_hexagono,
    tablero_a_api,
    tablero_desde_api,
)

#: Lado del lienzo rectificado del método de respaldo, en píxeles.
LADO = 900

#: Por debajo de esta confianza, la interfaz pide revisar el terreno.
CONFIANZA_DUDOSA = 0.55

#: Rangos de tono, saturación y valor (HSV de OpenCV, H de 0 a 179) de cada
#: terreno. Son rangos INICIALES, estimados a ojo sobre los colores del juego: NO
#: están calibrados con fotos de celular. Con la foto de referencia del tablero de
#: principiantes aciertan 19/19 una vez que se muestrea en el lugar correcto. Se
#: calibran con scripts/calibrar_vision.py.
RANGOS = {
    "bosque":   {"h": (30, 85),   "s": (60, 255), "v": (30, 165)},
    "pastos":   {"h": (30, 85),   "s": (40, 255), "v": (150, 255)},
    "campos":   {"h": (18, 35),   "s": (90, 255), "v": (140, 255)},
    "colinas":  {"h": (0, 18),    "s": (80, 255), "v": (70, 230)},
    "montanas": {"h": (0, 179),   "s": (0, 60),   "v": (60, 190)},
    "desierto": {"h": (15, 35),   "s": (10, 80),  "v": (170, 255)},
}


def leer_tablero(imagen_bytes: bytes) -> RespuestaVision:
    """
    Detecta terrenos y números a partir de la foto de un tablero vacío.

    Los puertos llegan como la plantilla del marco: el usuario los confirma al
    revisar, igual que los terrenos y números dudosos.

    Parameters
    ----------
    imagen_bytes : bytes
        La imagen tal como llegó del cliente.

    Returns
    -------
    RespuestaVision
        Tablero reconstruido, detecciones con su confianza y avisos.
    """
    imagen = _decodificar(imagen_bytes)
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    red = fichas.encontrar_red(imagen, hsv)

    if red is not None:
        detecciones, avisos_lectura = _leer_con_fichas(imagen, hsv, red)
    else:
        detecciones = _leer_por_borde(imagen)
        avisos_lectura = [
            "No encontré las fichas numéricas: los terrenos se leyeron por el borde del "
            "tablero y los números no se leyeron. Revisa todo."
        ]

    por_coord = {d.id: d for d in detecciones}
    tablero = tablero_desde_api({
        "hexagonos": [
            {"q": c[0], "r": c[1], "terreno": por_coord[id_hexagono(c)].terreno,
             "numero": por_coord[id_hexagono(c)].numero}
            for c in coordenadas_hexagonos()
        ],
        "puertos": [],
    })
    # La foto no lee los puertos: se parte de la plantilla del marco, que el
    # usuario confirma o corrige en la pantalla de revisión.
    tablero["puertos"] = plantilla_de_puertos(tablero["hexagonos"])

    avisos = avisos_lectura + avisos_del_tablero(tablero)
    avisos.append("Los puertos son una plantilla del marco: confírmalos o corrígelos.")

    return RespuestaVision(
        tablero=Tablero(**tablero_a_api(tablero)),
        detecciones=detecciones,
        avisos=avisos,
        mensaje=_mensaje(detecciones, leyo_numeros=red is not None),
    )


def _leer_con_fichas(
    imagen: np.ndarray, hsv: np.ndarray, red: fichas.Red
) -> tuple[list, list[str]]:
    """Terrenos y números sobre la red ajustada con las fichas, y avisos de lectura."""
    coords = coordenadas_hexagonos()
    centros = {c: red.centro(c) for c in coords}
    avisos = []

    # El desierto es el hexágono sin número (sin tinta en el centro) y de arena. Se
    # usan las dos pistas: un número de trazo fino, como el 2, tiene poca tinta, y
    # solo con ella se confundía con el desierto.
    presencia = {c: fichas.tinta_central(hsv, *centros[c], red.radio_ficha) for c in coords}
    tinta_max = max(max(presencia.values()), 1e-6)
    arena = {c: _arena(fichas.pixeles_de_terreno(imagen, red, c)) for c in coords}
    desierto = max(coords, key=lambda c: 0.8 * arena[c] - presencia[c] / tinta_max)
    resto = sorted(presencia[c] for c in coords if c != desierto)
    # Confianza: qué tan claro es que ahí no hay ficha y en los demás sí.
    separacion = (resto[0] - presencia[desierto]) / max(resto[0], 1e-6)
    confianza_desierto = float(np.clip(separacion, 0, 1))
    if presencia[desierto] >= 0.5 * float(np.median(resto)):
        avisos.append(
            "El desierto parece tener una ficha numérica; en el juego base no lleva "
            "número. Revisa el desierto y los números."
        )

    # Los otros 18 se reparten por color respetando el juego base (4 bosques, 4
    # pastos, 4 campos, 3 colinas, 3 montañas). Tienen ficha, así que no son desierto
    # aunque el color se le parezca.
    puntajes = {
        c: _puntajes_de_terreno(fichas.pixeles_de_terreno(imagen, red, c), excluir={"desierto"})
        for c in coords
        if c != desierto
    }
    reparto = Counter(TERRENOS)
    del reparto["desierto"]
    terrenos = {
        c: (terreno, confianza_de_terreno(margen))
        for c, (terreno, margen) in fichas.asignar_con_reparto(puntajes, reparto).items()
    }
    terrenos[desierto] = ("desierto", confianza_desierto)
    # Qué otros terrenos serían posibles, para ofrecerlos al revisar y para que la
    # interfaz reacomode el reparto cuando el usuario corrige uno.
    colores = {
        c: _puntajes_de_terreno(fichas.pixeles_de_terreno(imagen, red, c)) for c in coords
    }
    colores[desierto]["desierto"] = 2.0

    con_ficha = {c: centros[c] for c in coords if c != desierto}
    giros = fichas.giros_de_fichas(imagen, con_ficha, red.radio_ficha)
    puntuaciones, estabilidad = {}, {}
    for c in con_ficha:
        puntos, estable = fichas.leer_ficha(imagen, *centros[c], red.radio_ficha, giros[c])
        if puntos:
            puntuaciones[c], estabilidad[c] = puntos, estable
    numeros = fichas.leer_numeros(puntuaciones)

    detecciones = []
    for c in coords:
        numero, margen = numeros.get(c, (None, 0.0))
        # Una lectura que cambia al mover el recorte un píxel no es segura.
        if estabilidad.get(c, 0.0) < fichas.ESTABILIDAD_MINIMA:
            margen = min(margen, fichas.MARGEN_SEGURO * 0.9)
        detecciones.append(HexagonoDetectado(
            id=id_hexagono(c),
            terreno=terrenos[c][0],
            numero=numero,
            confianza_terreno=round(terrenos[c][1], 2),
            confianza_numero=round(fichas.confianza_de_margen(margen), 2) if numero else 0.0,
            opciones_numero=_ordenadas(puntuaciones.get(c, {})),
            opciones_terreno=_ordenadas(colores[c]),
        ))
    return detecciones, avisos


def _ordenadas(puntos: dict) -> list:
    """Las etiquetas de la más a la menos probable."""
    return sorted(puntos, key=lambda k: -puntos[k])


def _arena(pixeles: np.ndarray) -> float:
    """
    Qué tanto parece arena del desierto el color típico (mediana) de un hexágono, de
    0 a 1.

    La arena es amarilla como los campos pero menos saturada: medido en las dos fotos
    de ejemplo, arena s ≈ 130–150 y campos s ≈ 175. Las montañas tienen tono parecido
    pero s < 60, por eso se exige s ≥ 90.
    """
    if len(pixeles) == 0:
        return 0.0
    hsv = cv2.cvtColor(pixeles.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV)
    h, s, v = np.median(hsv.reshape(-1, 3), axis=0)
    if not (12 <= h <= 32 and s >= 90 and v >= 150):
        return 0.0
    return float(np.clip((165 - s) / 40, 0, 1))


def _leer_por_borde(imagen: np.ndarray) -> list:
    """Respaldo sin fichas: enderezar por el borde y clasificar parches (sin números)."""
    rectificada, _ = _rectificar(imagen)
    detecciones = []
    for coord in coordenadas_hexagonos():
        terreno, confianza = _clasificar_terreno(_parche_del_hexagono(rectificada, coord))
        detecciones.append(HexagonoDetectado(
            id=id_hexagono(coord), terreno=terreno, numero=None,
            confianza_terreno=round(confianza, 2), confianza_numero=0.0,
        ))
    return detecciones


def _mensaje(detecciones: list, leyo_numeros: bool) -> str:
    terrenos = sum(1 for d in detecciones if d.confianza_terreno < CONFIANZA_DUDOSA)
    if not leyo_numeros:
        return (
            f"{terrenos} terrenos quedaron con baja confianza y los números no se leyeron. "
            "Revisa los terrenos y escribe los números antes de calcular."
        )
    numeros = sum(
        1 for d in detecciones if d.terreno != "desierto" and d.confianza_numero < 0.5
    )
    if terrenos == 0 and numeros == 0:
        return "Leí los 19 terrenos y los 18 números. Échales un vistazo y confirma."
    return (
        f"Leí terrenos y números. Revisa los marcados: {terrenos} terrenos y {numeros} "
        "números quedaron dudosos."
    )


# ---------------------------------------------------------------------------
# Pasos
# ---------------------------------------------------------------------------

def _decodificar(datos: bytes) -> np.ndarray:
    """Bytes a imagen BGR, reescalada para que el proceso no dependa del tamaño."""
    arreglo = np.frombuffer(datos, dtype=np.uint8)
    imagen = cv2.imdecode(arreglo, cv2.IMREAD_COLOR)
    if imagen is None:
        raise ValueError("No se pudo leer la imagen")
    alto, ancho = imagen.shape[:2]
    escala = 1400 / max(alto, ancho)
    if escala < 1:
        imagen = cv2.resize(imagen, None, fx=escala, fy=escala,
                            interpolation=cv2.INTER_AREA)
    return imagen


def _rectificar(imagen: np.ndarray) -> tuple[np.ndarray, bool]:
    """
    Endereza el tablero a una vista cenital cuadrada.

    Busca el contorno más grande que no sea fondo, le ajusta un cuadrilátero y
    calcula la homografía hacia un lienzo canónico. Si no encuentra un contorno
    razonable, devuelve la imagen recortada al centro y avisa: es preferible una
    lectura mediocre que el usuario corrige, a un error que lo deja sin nada.
    """
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)

    # El tablero es la región con color; la mesa y el mar impreso suelen ser
    # más planos. Se toma saturación o brillo medio como indicio de "ficha".
    _, s, v = cv2.split(hsv)
    mascara = cv2.inRange(s, 40, 255) | cv2.inRange(v, 40, 250)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))

    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contornos:
        mayor = max(contornos, key=cv2.contourArea)
        if cv2.contourArea(mayor) > 0.15 * imagen.shape[0] * imagen.shape[1]:
            esquinas = _cuatro_esquinas(mayor)
            if esquinas is not None:
                destino = np.float32([[0, 0], [LADO, 0], [LADO, LADO], [0, LADO]])
                matriz = cv2.getPerspectiveTransform(esquinas, destino)
                return cv2.warpPerspective(imagen, matriz, (LADO, LADO)), True

    return cv2.resize(imagen, (LADO, LADO), interpolation=cv2.INTER_AREA), False


def _cuatro_esquinas(contorno: np.ndarray) -> np.ndarray | None:
    """
    Las cuatro esquinas del contorno, ordenadas desde arriba a la izquierda.

    Se usa el rectángulo de área mínima en vez de aproximar el polígono: el
    tablero es hexagonal, así que aproximarlo daría seis vértices y no cuatro,
    y lo que hace falta para la homografía son cuatro puntos.
    """
    caja = cv2.boxPoints(cv2.minAreaRect(contorno)).astype(np.float32)
    suma = caja.sum(axis=1)
    resta = np.diff(caja, axis=1).ravel()
    return np.float32([
        caja[np.argmin(suma)],   # arriba izquierda
        caja[np.argmin(resta)],  # arriba derecha
        caja[np.argmax(suma)],   # abajo derecha
        caja[np.argmax(resta)],  # abajo izquierda
    ])


def _centro_en_lienzo(q: int, r: int) -> tuple[int, int]:
    """Dónde cae el centro de un hexágono en el lienzo rectificado."""
    # El tablero abarca 5 hexágonos de ancho y 5 filas de alto.
    paso_x = LADO / 5.6
    paso_y = LADO / 5.3
    x = LADO / 2 + paso_x * (q + r / 2)
    y = LADO / 2 + paso_y * r
    return int(x), int(y)


def _parche_del_hexagono(imagen: np.ndarray, coord: tuple[int, int]) -> np.ndarray:
    """
    Recorta el interior de un hexágono, evitando su ficha numérica.

    Se toma un anillo alrededor del centro en vez de un cuadrado centrado: la
    ficha numérica ocupa justo el centro y falsearía el color del terreno.
    """
    x, y = _centro_en_lienzo(*coord)
    radio = int(LADO / 16)
    alto, ancho = imagen.shape[:2]
    x0, x1 = max(0, x - radio), min(ancho, x + radio)
    y0, y1 = max(0, y - radio), min(alto, y + radio)
    parche = imagen[y0:y1, x0:x1]
    if parche.size == 0:
        return np.zeros((4, 4, 3), dtype=np.uint8)

    # Se anula el centro, donde va la ficha.
    recorte = parche.copy()
    ch, cw = recorte.shape[:2]
    mascara = np.ones((ch, cw), dtype=bool)
    cv2.circle(
        mascara.view(np.uint8), (cw // 2, ch // 2), int(min(ch, cw) * 0.42), 0, -1
    )
    return recorte[mascara]


#: Margen de puntaje de terreno (proporción de píxeles) que se considera seguro al
#: repartir los terrenos: con él la confianza llega a 1.
MARGEN_TERRENO_SEGURO = 0.3


def confianza_de_terreno(margen: float) -> float:
    """Margen del reparto de terrenos → confianza 0–1 (0.55 es la frontera de revisión)."""
    return float(np.clip(margen / MARGEN_TERRENO_SEGURO, 0.0, 1.0))


def _puntajes_de_terreno(parche: np.ndarray, excluir: set | None = None) -> dict[str, float]:
    """Qué proporción de los píxeles del parche cae en el rango de cada terreno."""
    pixeles = parche.reshape(-1, 3).astype(np.uint8)
    if len(pixeles) < 10:
        return {}
    hsv = cv2.cvtColor(pixeles.reshape(1, -1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    puntajes = {}
    for terreno, rango in RANGOS.items():
        if excluir and terreno in excluir:
            continue
        dentro = (
            (h >= rango["h"][0]) & (h <= rango["h"][1])
            & (s >= rango["s"][0]) & (s <= rango["s"][1])
            & (v >= rango["v"][0]) & (v <= rango["v"][1])
        )
        puntajes[terreno] = float(dentro.mean())
    return puntajes


def _clasificar_terreno(parche: np.ndarray, excluir: set | None = None) -> tuple[str, float]:
    """
    Decide el terreno de un parche por su color, sin mirar el reparto (método del
    borde).

    Devuelve el nombre y una confianza entre 0 y 1: qué proporción de los píxeles
    del parche cae dentro del rango del terreno ganador. Una confianza baja
    significa que la interfaz debe pedir revisión, no que la lectura sea inútil.
    """
    puntajes = _puntajes_de_terreno(parche, excluir)
    if not puntajes:
        return "desierto", 0.0

    ganador = max(puntajes, key=puntajes.get)
    mejor = puntajes[ganador]
    segundo = sorted(puntajes.values())[-2] if len(puntajes) > 1 else 0.0

    # La confianza castiga los empates: si dos terrenos puntúan parecido, la
    # lectura es dudosa aunque el ganador tenga una proporción alta.
    confianza = mejor * (1 - segundo / mejor) if mejor > 0 else 0.0
    return ganador, float(np.clip(confianza, 0, 1))
