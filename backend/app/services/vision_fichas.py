"""
Fichas numéricas: dónde están los hexágonos y qué número tiene cada uno.

Las fichas son discos crema muy característicos, y cada una marca el centro exacto de
su hexágono. Por eso la visión parte de ellas en vez de adivinar la cuadrícula a
partir del borde del tablero, que falla en cuanto el fondo no es liso:

1. ``detectar_fichas``: círculos de Hough validados por el crema de su anillo
   exterior (ahí nunca hay tinta). Bastan unas pocas fichas seguras.
2. ``ajustar_red``: con esas fichas se ajusta la red hexagonal (RANSAC) y una
   homografía de las coordenadas canónicas a la foto, que da los 19 centros.
3. ``leer_numeros``: cada ficha se describe con rasgos que no dependen de la
   tipografía (rojo, dígitos, agujeros, pips) y se asignan números respetando el
   reparto del juego base. Las lecturas con poco margen quedan como dudosas.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

from app.domain.tablero import FICHAS, PIPS, coordenadas_hexagonos

RAIZ3 = math.sqrt(3)
TIERRA = set(coordenadas_hexagonos())

#: Fichas seguras mínimas para ajustar la red. Con menos se usa el método del borde.
MIN_FICHAS = 4

#: Margen de puntuación por debajo del cual un número se marca para revisión.
MARGEN_SEGURO = 1.5

#: Lado del recorte de cada ficha, en píxeles: se amplía para contar pips pequeños.
LADO_FICHA = 200

#: Radios de ficha que se prueban, como fracción del lado mayor de la foto. Con un
#: solo rango amplio, círculos falsos grandes (sobre la arena o los campos) fijaban
#: el radio típico y se descartaban las fichas reales, que en una foto de todo el
#: tablero miden en torno al 2.5 % del lado.
BANDAS_DE_RADIO = [(0.015, 0.03), (0.025, 0.045), (0.04, 0.07)]

#: Tinta mínima en el centro para aceptar un círculo como ficha: toda ficha tiene
#: número; un círculo de arena o de trigo, no.
TINTA_MINIMA = 0.02


# --- 1. Fichas seguras ----------------------------------------------------------------


def _anillo(
    forma: tuple[int, int], x: float, y: float, r_in: float, r_out: float
) -> np.ndarray:
    mascara = np.zeros(forma, np.uint8)
    cv2.circle(mascara, (int(x), int(y)), max(1, int(r_out)), 255, -1)
    if r_in > 0:
        cv2.circle(mascara, (int(x), int(y)), int(r_in), 0, -1)
    return mascara > 0


def crema(
    hsv: np.ndarray, x: float, y: float, r: float, r_in: float = 0.72, r_out: float = 0.92
) -> float:
    """
    Proporción de píxeles color crema en un anillo del círculo. Por defecto el anillo
    exterior de la ficha: ahí no llegan ni el número ni los pips.
    """
    zona = _anillo(hsv.shape[:2], x, y, r_in * r, r_out * r)
    h, s, v = (canal[zona] for canal in cv2.split(hsv))
    if h.size == 0:
        return 0.0
    return float(((h >= 8) & (h <= 32) & (s >= 25) & (s <= 130) & (v >= 170)).mean())


def tinta_central(hsv: np.ndarray, x: float, y: float, r: float) -> float:
    """
    Proporción de tinta (negra o roja) en el centro del círculo: ahí va el número.

    Sirve para encontrar el desierto, el único hexágono sin ficha. No basta con el
    color crema: la arena del desierto también es crema; lo que no tiene es número.
    """
    zona = _anillo(hsv.shape[:2], x, y, 0, 0.5 * r)
    h, s, v = (canal[zona] for canal in cv2.split(hsv))
    if h.size == 0:
        return 0.0
    rojo = ((h <= 12) | (h >= 165)) & (s >= 90) & (v >= 80)
    return float(((v <= 100) | rojo).mean())


def encontrar_red(imagen: np.ndarray, hsv: np.ndarray) -> Red | None:
    """
    La red hexagonal de la foto, probando cada banda de radio de ficha.

    No se sabe de antemano a qué distancia se tomó la foto; se queda la banda cuya
    red explica más fichas.
    """
    mejor: Red | None = None
    for banda in BANDAS_DE_RADIO:
        seguras, radio = detectar_fichas(imagen, hsv, banda)
        red = ajustar_red(seguras, radio, hsv)
        if red is not None and (mejor is None or red.fichas > mejor.fichas):
            mejor = red
    return mejor


def detectar_fichas(
    imagen: np.ndarray, hsv: np.ndarray, banda: tuple[float, float] = BANDAS_DE_RADIO[1]
) -> tuple[np.ndarray, float]:
    """
    Centros de las fichas seguras y su radio típico, buscando radios dentro de
    ``banda`` (fracciones del lado mayor de la foto).

    Hough encuentra también círculos falsos (piedras, barcos, bordes); se quedan los
    de anillo crema con tinta en el centro, radio parecido al de las mejores y sin
    solaparse.
    """
    alto, ancho = imagen.shape[:2]
    lado = max(alto, ancho)
    r_min, r_max = int(lado * banda[0]), int(lado * banda[1])
    gris = cv2.GaussianBlur(cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY), (5, 5), 1.2)
    candidatos = cv2.HoughCircles(
        gris,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=3 * r_min,
        param1=100,
        param2=14,
        minRadius=r_min,
        maxRadius=r_max,
    )
    if candidatos is None:
        return np.empty((0, 2)), 0.0
    puntuados = sorted(
        (
            (crema(hsv, x, y, r), x, y, r)
            for x, y, r in candidatos[0]
            if tinta_central(hsv, x, y, r) > TINTA_MINIMA
        ),
        reverse=True,
    )
    puntuados = [p for p in puntuados if p[0] >= 0.6]
    if not puntuados:
        return np.empty((0, 2)), 0.0
    r_tipico = float(np.median([r for _, _, _, r in puntuados[:8]]))
    seguras: list[tuple[float, float]] = []
    for _, x, y, r in puntuados:
        if abs(r - r_tipico) > 0.25 * r_tipico:
            continue
        if all(math.hypot(x - a, y - b) > 1.5 * r_tipico for a, b in seguras):
            seguras.append((float(x), float(y)))
    return np.array(seguras).reshape(-1, 2), r_tipico


# --- 2. Red hexagonal -------------------------------------------------------------------


def _girar(w: np.ndarray, grados: float) -> np.ndarray:
    a = math.radians(grados)
    return np.array(
        [w[0] * math.cos(a) - w[1] * math.sin(a), w[0] * math.sin(a) + w[1] * math.cos(a)]
    )


def _redondear_axial(q: float, r: float) -> tuple[int, int]:
    """Redondeo a la celda hexagonal más cercana (en coordenadas cúbicas)."""
    x, z = q, r
    y = -x - z
    rx, ry, rz = round(x), round(y), round(z)
    dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return int(rx), int(rz)


def canonico(q: float, r: float) -> tuple[float, float]:
    """Centro de un hexágono en el plano canónico (tamaño 1, punta arriba)."""
    return RAIZ3 * (q + r / 2), 1.5 * r


@dataclass
class Red:
    """La red ajustada: homografía del plano canónico a la foto."""

    homografia: np.ndarray
    radio_ficha: float
    fichas: int

    def a_imagen(self, puntos) -> np.ndarray:
        pts = np.float32(puntos).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(pts, self.homografia).reshape(-1, 2)

    def centro(self, coord: tuple[int, int]) -> tuple[float, float]:
        x, y = self.a_imagen([canonico(*coord)])[0]
        return float(x), float(y)


def _es_tierra(hsv: np.ndarray, x: float, y: float) -> bool:
    alto, ancho = hsv.shape[:2]
    if not (0 <= x < ancho and 0 <= y < alto):
        return False
    h, s, v = hsv[int(y), int(x)]
    mar = 90 <= h <= 130 and s > 60
    fondo_claro = s < 20 and v > 225
    return not (mar or fondo_claro)


def ajustar_red(
    fichas: np.ndarray, r_tipico: float, hsv: np.ndarray, semilla: int = 0
) -> Red | None:
    """
    La red hexagonal que mejor explica las fichas seguras, o None si no hay forma.

    RANSAC: se toma una pareja de fichas como vecinas, se construye la red y se
    cuentan las fichas que encajan en ella. Luego se fija la orientación (el eje q
    apunta a la derecha, como en el dominio) y el origen (todas las fichas dentro del
    tablero de 19 y tierra bajo los 19 centros).
    """
    if len(fichas) < MIN_FICHAS:
        return None
    aleatorio = random.Random(semilla)
    paso_esperado = 5 * r_tipico  # entre fichas vecinas hay unos 5 radios de ficha

    def red(origen, u):
        v = _girar(u, 60)
        base = np.array([u, v]).T
        return (lambda q, r: origen + q * u + r * v), (
            lambda p: np.linalg.solve(base, p - origen)
        )

    mejor: tuple[int, np.ndarray, np.ndarray] | None = None
    for _ in range(400):
        i, j = aleatorio.sample(range(len(fichas)), 2)
        u = fichas[j] - fichas[i]
        if not 0.6 * paso_esperado < np.linalg.norm(u) < 1.6 * paso_esperado:
            continue
        a_img, a_axial = red(fichas[i], u)
        dentro = sum(
            np.linalg.norm(a_img(*_redondear_axial(*a_axial(p))) - p) < 0.25 * np.linalg.norm(u)
            for p in fichas
        )
        if mejor is None or dentro > mejor[0]:
            mejor = (dentro, fichas[i], u)
    if mejor is None or mejor[0] < MIN_FICHAS:
        return None

    # La pareja al azar puede dar cualquiera de los 6 vecinos como vector base: se
    # gira de 60 en 60 hasta que apunte a la derecha, o la lectura sale rotada.
    _, origen, u = mejor
    u = min((_girar(u, 60 * k) for k in range(6)), key=lambda w: abs(math.atan2(w[1], w[0])))
    a_img, a_axial = red(origen, u)
    asignadas = []
    for p in fichas:
        c = _redondear_axial(*a_axial(p))
        if np.linalg.norm(a_img(*c) - p) < 0.25 * np.linalg.norm(u):
            asignadas.append((c, p))

    # El origen: todas las fichas dentro del tablero y, entre los empates, más tierra
    # bajo los 19 centros (así no se elige una red corrida hacia el mar).
    opciones = []
    for dq in range(-4, 5):
        for dr in range(-4, 5):
            if all((q + dq, r + dr) in TIERRA for (q, r), _ in asignadas):
                tierra = sum(_es_tierra(hsv, *a_img(q - dq, r - dr)) for q, r in TIERRA)
                opciones.append((tierra, dq, dr))
    if not opciones:
        return None
    _, dq, dr = max(opciones)
    canon = np.float32([canonico(q + dq, r + dr) for (q, r), _ in asignadas])
    foto = np.float32([p for _, p in asignadas])
    # RANSAC con umbral estricto (15 % de la distancia entre fichas): un círculo que
    # pasó por ficha sin serlo se descarta en vez de promediarse y torcer la red. Con
    # mínimos cuadrados, un solo falso positivo movía los centros hasta 12 px.
    umbral = 0.15 * float(np.linalg.norm(u))
    homografia, validas = cv2.findHomography(canon, foto, cv2.RANSAC, umbral)
    if homografia is None or validas is None or int(validas.sum()) < MIN_FICHAS:
        return None
    return Red(homografia=homografia, radio_ficha=r_tipico, fichas=int(validas.sum()))


def pixeles_de_terreno(imagen: np.ndarray, red: Red, coord: tuple[int, int]) -> np.ndarray:
    """Los píxeles BGR del anillo de terreno de un hexágono que caen dentro de la foto."""
    alto, ancho = imagen.shape[:2]
    puntos = muestras_de_terreno(red, coord).astype(int)
    x, y = puntos[:, 0], puntos[:, 1]
    dentro = (x >= 0) & (x < ancho) & (y >= 0) & (y < alto)
    return imagen[y[dentro], x[dentro]]


def muestras_de_terreno(red: Red, coord: tuple[int, int]) -> np.ndarray:
    """
    Puntos de un anillo entre la ficha y el borde de la pieza (0.5–0.78 del tamaño
    del hexágono): ni la ficha ni el borde beige de la pieza falsean el color.
    """
    cx, cy = canonico(*coord)
    puntos = [
        (cx + rad * math.cos(a), cy + rad * math.sin(a))
        for rad in np.linspace(0.5, 0.78, 6)
        for a in np.linspace(0, 2 * math.pi, 36, endpoint=False)
    ]
    return red.a_imagen(puntos)


# --- 3. Números -------------------------------------------------------------------------

#: Cuántos dígitos tiene cada número.
DIGITOS = {n: 2 if n >= 10 else 1 for n in PIPS if n != 7}

#: Agujeros esperados y cuánto convence cada cantidad. En la tipografía de Catan el 4
#: es abierto (0 agujeros), pero un 4 cerrado no se descarta del todo; y en otras
#: tipografías el 1 del 10 cierra un hueco con su base.
AGUJEROS = {
    2: {0: 1.0},
    3: {0: 1.0},
    4: {0: 1.0, 1: 0.3},
    5: {0: 1.0},
    6: {1: 1.0},
    8: {2: 1.0},
    9: {1: 1.0},
    10: {1: 1.0, 2: 0.5},
    11: {0: 1.0},
    12: {0: 1.0},
}


#: Tinta en la zona superior derecha del dígito por encima de la cual se considera
#: cerrado (un 8) y no abierto (un 6). Medido en la foto de referencia: el 6 da
#: 0.62–0.71 y el 8, 0.89–1.0.
ABERTURA_CERRADA = 0.8

#: Recortes ligeramente distintos con los que se relee cada ficha (dx, dy, escala).
#: Una lectura solo es segura si no cambia entre ellos: en fotos pequeñas o muy
#: comprimidas un píxel mueve los rasgos.
PERTURBACIONES = [
    (0.0, 0.0, 1.0),
    (1.5, 0.0, 1.0),
    (-1.5, 0.0, 1.0),
    (0.0, 1.5, 1.0),
    (0.0, -1.5, 1.0),
    (0.0, 0.0, 0.94),
    (0.0, 0.0, 1.06),
]

#: Fracción de relecturas que deben coincidir para que una ficha no quede dudosa.
ESTABILIDAD_MINIMA = 0.8


@dataclass
class Rasgos:
    rojo: bool
    digitos: int
    agujeros: int
    pips: int
    #: Tinta arriba a la derecha del dígito: el 6 está abierto ahí y el 8 no. Es una
    #: segunda pista para separarlos, independiente de los agujeros.
    abertura: float | None = None


#: Giros que se prueban cuando no se puede saber cómo está la ficha.
GIROS_A_PROBAR = (0.0, 90.0, 180.0, 270.0)

#: Una ficha cuyo giro se aparta del de la mayoría más que esto está volteada de
#: verdad; si se aparta menos, la diferencia es ruido al contar pips de 1–2 px.
DESVIO_PROPIO = 40.0

#: Cuánto pueden diferir dos giros para contarse en el mismo grupo al buscar el giro
#: de la mayoría. Ambos valores se eligieron probando varias combinaciones sobre las
#: dos fotos de ejemplo (giradas 0, 90, 180, 25 y −40 grados) y tableros sintéticos.
ANCHO_GRUPO = 30.0


def _recorte(
    imagen: np.ndarray, x: float, y: float, r: float, giro: float = 0.0
) -> np.ndarray | None:
    """La ficha ampliada a ``LADO_FICHA`` y girada ``giro`` grados (antihorario)."""
    t = int(r * 1.05)
    x0, y0 = int(x) - t, int(y) - t
    if x0 < 0 or y0 < 0 or x0 + 2 * t > imagen.shape[1] or y0 + 2 * t > imagen.shape[0]:
        return None
    recorte = cv2.resize(
        imagen[y0 : y0 + 2 * t, x0 : x0 + 2 * t],
        (LADO_FICHA, LADO_FICHA),
        interpolation=cv2.INTER_CUBIC,
    )
    if giro:
        medio = LADO_FICHA / 2
        matriz = cv2.getRotationMatrix2D((medio, medio), giro, 1.0)
        recorte = cv2.warpAffine(
            recorte, matriz, (LADO_FICHA, LADO_FICHA), borderMode=cv2.BORDER_REPLICATE
        )
    return recorte


def orientacion_de_ficha(imagen: np.ndarray, x: float, y: float, r: float) -> float | None:
    """
    Cuánto girar la ficha para que quede derecha, o None si no se puede saber.

    Los pips siempre van debajo del número: la dirección del número a los pips es
    "abajo". Así se leen igual una foto girada y una ficha puesta de lado en la mesa.
    """
    recorte = _recorte(imagen, x, y, r)
    if recorte is None:
        return None
    h, s, v = cv2.split(cv2.cvtColor(recorte, cv2.COLOR_BGR2HSV))
    medio = LADO_FICHA // 2
    dentro = np.zeros((LADO_FICHA, LADO_FICHA), np.uint8)
    cv2.circle(dentro, (medio, medio), int(LADO_FICHA * 0.42), 255, -1)
    tinta = ((((h <= 12) | (h >= 165)) & (s >= 55) & (v >= 80)) | (v <= 130)) & (dentro > 0)
    n, _, stats, centros = cv2.connectedComponentsWithStats(tinta.astype(np.uint8), 8)
    lado_min, area_min = LADO_FICHA * 0.22, LADO_FICHA * LADO_FICHA * 0.006
    grandes = [
        k for k in range(1, n)
        if max(stats[k, cv2.CC_STAT_WIDTH], stats[k, cv2.CC_STAT_HEIGHT]) >= lado_min
        and stats[k, cv2.CC_STAT_AREA] >= area_min
    ]
    pips = [
        k for k in range(1, n)
        if k not in grandes and 4 <= stats[k, cv2.CC_STAT_AREA] <= 200
    ]
    if not grandes or not pips:
        return None
    numero = np.average(
        centros[grandes], axis=0, weights=stats[grandes, cv2.CC_STAT_AREA]
    )
    abajo = centros[pips].mean(axis=0) - numero
    if np.linalg.norm(abajo) < LADO_FICHA * 0.1:
        return None
    # En la imagen el eje y crece hacia abajo: "abajo" es el ángulo 90°. Girar la
    # ficha θ grados en sentido antihorario resta θ a ese ángulo.
    return math.degrees(math.atan2(abajo[1], abajo[0])) - 90.0


def _diferencia_angular(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def giros_de_fichas(
    imagen: np.ndarray, centros: dict, r: float
) -> dict:
    """
    Cuánto enderezar cada ficha: centro → grados, o None si hay que probar giros.

    La medida de una sola ficha es ruidosa (sus pips miden 1–2 px), pero en una foto
    la mayoría de las fichas comparten el giro de la cámara. Se usa ese giro común,
    salvo en las fichas que se apartan claramente de él: esas están puestas al revés
    o de lado en la mesa y se enderezan con su propia medida.
    """
    propios = {c: orientacion_de_ficha(imagen, x, y, r) for c, (x, y) in centros.items()}
    medidos = [g for g in propios.values() if g is not None]
    if len(medidos) < 3:
        return propios
    # El giro común es el del grupo más grande de fichas con giros parecidos, no el
    # promedio de todas: si la mitad está de lado, el promedio no sirve a ninguna.
    grupo = max(
        ([g for g in medidos if _diferencia_angular(g, centro) <= ANCHO_GRUPO]
         for centro in medidos),
        key=len,
    )
    radianes = np.radians(grupo)
    comun = math.degrees(math.atan2(np.sin(radianes).mean(), np.cos(radianes).mean()))
    return {
        c: g if g is not None and _diferencia_angular(g, comun) > DESVIO_PROPIO else comun
        for c, g in propios.items()
    }


def rasgos_de_ficha(
    imagen: np.ndarray, x: float, y: float, r: float, giro: float = 0.0
) -> Rasgos | None:
    """
    Lo que se ve en una ficha, sin intentar reconocer la forma de cada dígito:
    si la tinta es roja, cuántos dígitos, cuántos agujeros y cuántos pips. ``giro``
    endereza la ficha antes de medir (ver ``orientacion_de_ficha``).
    """
    recorte = _recorte(imagen, x, y, r, giro)
    if recorte is None:
        return None
    h, s, v = cv2.split(cv2.cvtColor(recorte, cv2.COLOR_BGR2HSV))
    medio = LADO_FICHA // 2
    dentro = np.zeros((LADO_FICHA, LADO_FICHA), np.uint8)
    cv2.circle(dentro, (medio, medio), int(LADO_FICHA * 0.4), 255, -1)
    dentro = dentro > 0

    rojo = ((h <= 12) | (h >= 165)) & (s >= 90) & (v >= 80)
    es_rojo = bool(rojo[dentro].mean() > 0.03)
    # Umbral adaptativo (Otsu) por ficha: con un umbral fijo el desenfoque rellena los
    # agujeros del 6 y del 8. La tinta negra se separa por brillo; la roja, por a* (Lab).
    canal = cv2.cvtColor(recorte, cv2.COLOR_BGR2LAB)[:, :, 1] if es_rojo else 255 - v
    umbral, _ = cv2.threshold(
        canal[dentro].reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    tinta = ((canal > umbral) & dentro).astype(np.uint8)

    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(tinta, 8)
    alto_min, area_min = LADO_FICHA * 0.22, LADO_FICHA * LADO_FICHA * 0.006
    grandes = [
        k
        for k in range(1, n)
        if stats[k, cv2.CC_STAT_HEIGHT] >= alto_min and stats[k, cv2.CC_STAT_AREA] >= area_min
    ]
    agujeros = 0
    for k in grandes:
        caja = stats[k, cv2.CC_STAT_WIDTH] * stats[k, cv2.CC_STAT_HEIGHT]
        contornos, jerarquia = cv2.findContours(
            (etiquetas == k).astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )
        if jerarquia is not None:
            agujeros += sum(
                1
                for e, c in zip(jerarquia[0], contornos, strict=True)
                if e[3] != -1 and cv2.contourArea(c) >= 0.02 * caja
            )

    # Pips: franja propia bajo el número, con umbrales más flojos (son puntos pequeños
    # y, en el 6 y el 8, de un rojo pálido).
    base = max(
        (stats[k, cv2.CC_STAT_TOP] + stats[k, cv2.CC_STAT_HEIGHT] for k in grandes),
        default=int(LADO_FICHA * 0.7),
    )
    franja = np.zeros_like(dentro)
    franja[
        base + 2 : min(LADO_FICHA, base + 40), int(LADO_FICHA * 0.2) : int(LADO_FICHA * 0.8)
    ] = True
    tinta_pips = (
        ((((h <= 12) | (h >= 165)) & (s >= 55) & (v >= 80)) | (v <= 130)) & franja & dentro
    )
    n_p, _, stats_p, _ = cv2.connectedComponentsWithStats(tinta_pips.astype(np.uint8), 8)
    pips = sum(1 for k in range(1, n_p) if 4 <= stats_p[k, cv2.CC_STAT_AREA] <= 200)

    abertura = None
    if es_rojo and grandes:
        k = max(grandes, key=lambda k: stats[k, cv2.CC_STAT_AREA])
        x0_, y0_, ancho_, alto_ = stats[k, :4]
        digito = (etiquetas == k)[y0_ : y0_ + alto_, x0_ : x0_ + ancho_]
        zona = digito[int(0.18 * alto_) : int(0.42 * alto_), int(0.62 * ancho_) :]
        abertura = float(zona.mean()) if zona.size else None

    return Rasgos(
        rojo=es_rojo, digitos=len(grandes), agujeros=agujeros, pips=pips, abertura=abertura
    )


def puntuar(rasgos: Rasgos) -> dict[int, float]:
    """
    Qué tanto encaja cada número con los rasgos. Las pistas fuertes (rojo, dígitos,
    agujeros) pesan más que los pips, que en fotos pequeñas se cuentan mal.
    """
    puntos = {}
    for n in DIGITOS:
        p = 3.0 if rasgos.rojo == (n in (6, 8)) else -3.0
        p += 2.0 if rasgos.digitos == DIGITOS[n] else -2.0
        p += 1.5 * AGUJEROS[n][rasgos.agujeros] if rasgos.agujeros in AGUJEROS[n] else -1.5
        p -= 0.7 * abs(rasgos.pips - PIPS[n])
        if rasgos.abertura is not None and n in (6, 8):
            # +1.5 a favor del 8 si está cerrado arriba a la derecha, del 6 si abierto.
            cerrado = float(np.clip((rasgos.abertura - ABERTURA_CERRADA) / 0.1, -1, 1))
            p += 1.5 * (cerrado if n == 8 else -cerrado)
        puntos[n] = p
    return puntos


def leer_ficha(
    imagen: np.ndarray, x: float, y: float, r: float, giro: float | None = None
) -> tuple[dict[int, float], float]:
    """
    Puntuación de una ficha promediada sobre recortes ligeramente distintos, y su
    estabilidad: qué fracción de esos recortes da el mismo número ganador.

    ``giro`` endereza la ficha (ver ``giros_de_fichas``); si es None se prueban los
    cuatro giros rectos y se queda el que da la lectura más clara.
    """
    if giro is not None:
        return _leer_con_giro(imagen, x, y, r, giro)
    lecturas = [_leer_con_giro(imagen, x, y, r, g) for g in GIROS_A_PROBAR]
    return max(lecturas, key=lambda lectura: _claridad(lectura[0]))


def _claridad(puntos: dict[int, float]) -> float:
    """Ventaja del mejor número sobre el segundo."""
    if len(puntos) < 2:
        return -math.inf
    primero, segundo = sorted(puntos.values(), reverse=True)[:2]
    return primero - segundo


def _leer_con_giro(
    imagen: np.ndarray, x: float, y: float, r: float, giro: float
) -> tuple[dict[int, float], float]:
    suma: dict[int, float] = {}
    ganadores = []
    for dx, dy, escala in PERTURBACIONES:
        rasgos = rasgos_de_ficha(imagen, x + dx, y + dy, r * escala, giro)
        if rasgos is None:
            continue
        puntos = puntuar(rasgos)
        ganadores.append(max(puntos, key=puntos.get))
        for n, valor in puntos.items():
            suma[n] = suma.get(n, 0.0) + valor
    if not ganadores:
        return {}, 0.0
    promedio = {n: valor / len(ganadores) for n, valor in suma.items()}
    mejor = max(promedio, key=promedio.get)
    return promedio, sum(g == mejor for g in ganadores) / len(ganadores)


def asignar_con_reparto(
    puntuaciones: dict, reparto: Counter
) -> dict:
    """
    La asignación de etiquetas (números o terrenos) que más puntúa en total
    respetando el reparto, y la seguridad de cada una.

    ``puntuaciones`` va de clave (coordenada) a {etiqueta: puntuación}; ``reparto``
    dice cuántas veces puede usarse cada etiqueta.

    Se resuelve con el algoritmo húngaro: cada copia del reparto es una "plaza" y
    cada ficha ocupa una. La seguridad de una ficha es cuánto baja la puntuación
    total si se le prohíbe su etiqueta y se reparte todo de nuevo. Así una ficha que
    por sí sola duda entre 3 y 4 queda segura si los dos 4 ya están claros en otras
    fichas, y dudosa si no.

    Returns
    -------
    dict
        Clave → (etiqueta, margen). Un margen pequeño pide revisión.
    """
    claves = list(puntuaciones)
    plazas = [etiqueta for etiqueta, k in reparto.items() for _ in range(k)]
    if not claves or len(claves) > len(plazas):
        return {}
    # Una etiqueta sin puntuación cuesta mucho, pero no infinito: así siempre hay
    # asignación aunque una ficha no se haya podido leer bien.
    costo = np.array(
        [[-puntuaciones[c].get(etiqueta, -10.0) for etiqueta in plazas] for c in claves]
    )
    filas, columnas = linear_sum_assignment(costo)
    total = costo[filas, columnas].sum()

    salida = {}
    for i, j in zip(filas, columnas, strict=True):
        etiqueta = plazas[j]
        prohibido = costo.copy()
        prohibido[i, [k for k, e in enumerate(plazas) if e == etiqueta]] = 1e6
        f2, c2 = linear_sum_assignment(prohibido)
        margen = float(prohibido[f2, c2].sum() - total)
        # Si la ficha no se lee a sí misma como esa etiqueta, la etiqueta es una
        # deducción del reparto, no una lectura: nunca es segura. Sin esta regla, una
        # ficha que parecía claramente un 6 recibía el 8 "sobrante" con margen alto.
        propio = max(puntuaciones[claves[i]].values(), default=-10.0)
        suyo = puntuaciones[claves[i]].get(etiqueta, -10.0)
        if suyo < propio:
            margen = min(margen, suyo - propio)
        salida[claves[i]] = (etiqueta, max(0.0, margen))
    return salida


def leer_numeros(
    puntuaciones: dict[tuple[int, int], dict[int, float]],
) -> dict[tuple[int, int], tuple[int, float]]:
    """
    Asigna un número a cada ficha respetando el reparto del juego base (una ficha de
    2 y de 12, dos de cada uno de los demás).

    Returns
    -------
    dict
        Coordenada → (número, margen). Un margen menor que ``MARGEN_SEGURO`` pide
        revisión manual.
    """
    return asignar_con_reparto(puntuaciones, Counter(FICHAS))


def confianza_de_margen(margen: float) -> float:
    """Margen de puntuación → confianza entre 0 y 1; 0.5 es la frontera de revisión."""
    return float(np.clip(margen / (2 * MARGEN_SEGURO), 0.0, 1.0))
