"""
Lectura del tablero a partir de una fotografía.

Estrategia
----------
El tablero de Catan tiene topología **fija**: 19 hexágonos en filas 3-4-5-4-3.
Eso permite evitar por completo la detección abierta de objetos:

1. Se aísla el tablero del fondo por color (todo lo que no es mesa ni mar).
2. Se ajusta un cuadrilátero a su contorno y se calcula una **homografía** que lo
   rectifica a una vista cenital canónica.
3. Con el tablero rectificado ya se sabe **exactamente** dónde cae cada hexágono,
   así que solo hay que clasificar 19 parches pequeños por su color.

El resultado nunca se da por definitivo: cada hexágono viaja con su confianza, y
la interfaz pide confirmación antes de calcular.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.domain.tablero import coordenadas_hexagonos
from app.schemas.api import HexagonoDetectado, RespuestaVision, Tablero
from app.services.serializers import (
    avisos_del_tablero,
    id_hexagono,
    tablero_a_api,
    tablero_desde_api,
)

#: Lado del lienzo rectificado, en píxeles.
LADO = 900

#: Rangos de tono, saturación y valor (HSV de OpenCV, H de 0 a 179) de cada
#: terreno. Medidos sobre fotos de tableros con iluminación de interior.
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
    rectificada, encontrado = _rectificar(imagen)

    detecciones = []
    terrenos, numeros = {}, {}
    for coord in coordenadas_hexagonos():
        parche = _parche_del_hexagono(rectificada, coord)
        terreno, confianza = _clasificar_terreno(parche)
        terrenos[coord] = terreno
        detecciones.append(
            HexagonoDetectado(
                id=id_hexagono(coord),
                terreno=terreno,
                numero=None,
                confianza_terreno=round(confianza, 2),
                confianza_numero=0.0,
            )
        )

    tablero = tablero_desde_api({
        "hexagonos": [
            {"q": c[0], "r": c[1], "terreno": terrenos[c], "numero": numeros.get(c)}
            for c in coordenadas_hexagonos()
        ],
        "puertos": [],
    })

    avisos = avisos_del_tablero(tablero)
    if not encontrado:
        avisos.insert(0, "No se localizó el borde del tablero; la lectura puede fallar.")

    dudosos = [d.id for d in detecciones if d.confianza_terreno < 0.55]
    mensaje = (
        "Revisa los terrenos marcados en amarillo y escribe los números. "
        "La foto no lee las fichas numéricas todavía."
    )
    if dudosos:
        mensaje = (
            f"{len(dudosos)} hexágonos quedaron con baja confianza. "
            "Revísalos y escribe los números antes de calcular."
        )

    return RespuestaVision(
        tablero=Tablero(**tablero_a_api(tablero)),
        detecciones=detecciones,
        avisos=avisos,
        mensaje=mensaje,
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


def _clasificar_terreno(parche: np.ndarray) -> tuple[str, float]:
    """
    Decide el terreno de un parche por su color.

    Devuelve el nombre y una confianza entre 0 y 1: qué proporción de los píxeles
    del parche cae dentro del rango del terreno ganador. Una confianza baja
    significa que la interfaz debe pedir revisión, no que la lectura sea inútil.
    """
    pixeles = parche.reshape(-1, 3).astype(np.uint8)
    if len(pixeles) < 10:
        return "desierto", 0.0

    hsv = cv2.cvtColor(pixeles.reshape(1, -1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]

    puntajes = {}
    for terreno, rango in RANGOS.items():
        dentro = (
            (h >= rango["h"][0]) & (h <= rango["h"][1])
            & (s >= rango["s"][0]) & (s <= rango["s"][1])
            & (v >= rango["v"][0]) & (v <= rango["v"][1])
        )
        puntajes[terreno] = float(dentro.mean())

    ganador = max(puntajes, key=puntajes.get)
    mejor = puntajes[ganador]
    segundo = sorted(puntajes.values())[-2] if len(puntajes) > 1 else 0.0

    # La confianza castiga los empates: si dos terrenos puntúan parecido, la
    # lectura es dudosa aunque el ganador tenga una proporción alta.
    confianza = mejor * (1 - segundo / mejor) if mejor > 0 else 0.0
    return ganador, float(np.clip(confianza, 0, 1))
