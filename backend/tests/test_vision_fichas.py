"""
Visión con fichas numéricas, sobre un tablero sintético dibujado con OpenCV.

La foto real de referencia no está en el repositorio (tiene derechos de autor); la
prueba con ella está en ``test_vision_foto_real.py`` y solo corre si existe. Esta
prueba sintética corre siempre: fichas crema con el número y sus pips, el desierto
sin ficha y un fondo de mesa, que es lo que confundía al método anterior.

La propiedad que más importa no es acertar todo, sino que **ninguna lectura
equivocada llegue con confianza alta**: lo dudoso se revisa a mano.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest

from app.domain.tablero import PIPS, coordenadas_hexagonos, generar_tablero
from app.services import vision, vision_fichas

FONDO_MADERA = (40, 80, 130)  # BGR
CREMA = (160, 205, 232)
ROJO = (30, 30, 215)
NEGRO = (25, 25, 25)


def _color_de(terreno: str) -> tuple[int, int, int]:
    rango = vision.RANGOS[terreno]
    hsv = np.uint8([[[sum(rango[c]) // 2 for c in ("h", "s", "v")]]])
    return tuple(int(x) for x in cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0])


def tablero_sintetico(tablero: dict, lado: int = 70, angulo: float = 0.0) -> bytes:
    """Un tablero con fichas sobre fondo de madera, opcionalmente girado."""
    lienzo = np.full((1000, 1100, 3), FONDO_MADERA, np.uint8)
    cx, cy = 550, 500
    giro = math.radians(angulo)

    def a_lienzo(x, y):
        return (
            cx + x * math.cos(giro) - y * math.sin(giro),
            cy + x * math.sin(giro) + y * math.cos(giro),
        )

    for (q, r), terreno in tablero["terrenos"].items():
        x, y = lado * math.sqrt(3) * (q + r / 2), lado * 1.5 * r
        esquinas = [
            a_lienzo(
                x + lado * 0.97 * math.cos(math.radians(60 * i - 90)),
                y + lado * 0.97 * math.sin(math.radians(60 * i - 90)),
            )
            for i in range(6)
        ]
        cv2.fillPoly(lienzo, [np.int32(esquinas)], _color_de(terreno))
        numero = tablero["numeros"].get((q, r))
        if numero is None:
            continue  # el desierto no lleva ficha
        fx, fy = (int(v) for v in a_lienzo(x, y))
        radio = int(lado * 0.36)
        cv2.circle(lienzo, (fx, fy), radio, CREMA, -1)
        cv2.circle(lienzo, (fx, fy), radio, (60, 90, 110), 2)
        tinta = ROJO if numero in (6, 8) else NEGRO
        texto = str(numero)
        (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_DUPLEX, 0.95, 3)
        cv2.putText(
            lienzo,
            texto,
            (fx - tw // 2, fy + th // 2 - 4),
            cv2.FONT_HERSHEY_DUPLEX,
            0.95,
            tinta,
            3,
            cv2.LINE_AA,
        )
        pips = PIPS[numero]
        for k in range(pips):
            px = fx + int((k - (pips - 1) / 2) * 8)
            cv2.circle(lienzo, (px, fy + int(radio * 0.7)), 2, tinta, -1)
    ok, datos = cv2.imencode(".png", lienzo)
    assert ok
    return datos.tobytes()


def _evaluar(tablero: dict, respuesta) -> dict:
    leidos = {(h.q, h.r): h for h in respuesta.tablero.hexagonos}
    detecciones = {d.id: d for d in respuesta.detecciones}
    terrenos = sum(leidos[c].terreno == t for c, t in tablero["terrenos"].items())
    numeros = errores_seguros = 0
    for c, n in tablero["numeros"].items():
        d = detecciones[f"{c[0]},{c[1]}"]
        if d.numero == n:
            numeros += 1
        elif d.confianza_numero >= 0.5:
            errores_seguros += 1
    return {"terrenos": terrenos, "numeros": numeros, "errores_seguros": errores_seguros}


@pytest.fixture(scope="module")
def tablero() -> dict:
    return generar_tablero(semilla=5)


@pytest.mark.parametrize("angulo", [0.0, 7.0])
def test_lee_un_tablero_sintetico_sobre_fondo_de_madera(tablero, angulo, capsys):
    respuesta = vision.leer_tablero(tablero_sintetico(tablero, angulo=angulo))
    medido = _evaluar(tablero, respuesta)
    with capsys.disabled():
        print(f"\n  sintético con fichas, giro {angulo}°: {medido}")

    desierto = next(c for c, t in tablero["terrenos"].items() if t == "desierto")
    assert (
        next(h for h in respuesta.tablero.hexagonos if (h.q, h.r) == desierto).terreno
        == "desierto"
    )
    assert medido["terrenos"] >= 17
    # Lo importante: ningún número equivocado con confianza alta.
    assert medido["errores_seguros"] == 0
    assert medido["numeros"] >= 12


def test_la_lectura_respeta_el_reparto_de_fichas(tablero):
    respuesta = vision.leer_tablero(tablero_sintetico(tablero))
    leidos = [h.numero for h in respuesta.tablero.hexagonos if h.numero]
    from collections import Counter

    from app.domain.tablero import FICHAS

    assert all(Counter(leidos)[n] <= Counter(FICHAS)[n] for n in Counter(leidos))


def test_sin_fichas_se_usa_el_respaldo_y_se_avisa():
    lienzo = np.full((600, 600, 3), FONDO_MADERA, np.uint8)
    ok, datos = cv2.imencode(".png", lienzo)
    respuesta = vision.leer_tablero(datos.tobytes())
    assert any("No encontré las fichas" in a for a in respuesta.avisos)
    assert all(d.numero is None for d in respuesta.detecciones)


# --- Piezas sueltas -------------------------------------------------------------------


def test_la_puntuacion_distingue_por_rasgos_fuertes():
    rasgos = vision_fichas.Rasgos(rojo=True, digitos=1, agujeros=2, pips=5)
    puntos = vision_fichas.puntuar(rasgos)
    assert max(puntos, key=puntos.get) == 8
    rasgos = vision_fichas.Rasgos(rojo=False, digitos=2, agujeros=1, pips=3)
    puntos = vision_fichas.puntuar(rasgos)
    assert max(puntos, key=puntos.get) == 10


def test_la_asignacion_no_repite_el_unico_2():
    # Dos fichas que "parecen" un 2: solo una puede serlo; la otra queda dudosa.
    parecido_a_2 = vision_fichas.puntuar(vision_fichas.Rasgos(False, 1, 0, 1))
    asignados = vision_fichas.leer_numeros({(0, 0): parecido_a_2, (1, 0): dict(parecido_a_2)})
    numeros = [n for n, _ in asignados.values()]
    assert numeros.count(2) == 1


def test_la_red_da_19_centros_distintos(tablero):
    datos = np.frombuffer(tablero_sintetico(tablero), np.uint8)
    imagen = cv2.imdecode(datos, cv2.IMREAD_COLOR)
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    seguras, radio = vision_fichas.detectar_fichas(imagen, hsv)
    red = vision_fichas.ajustar_red(seguras, radio, hsv)
    assert red is not None
    centros = {tuple(np.round(red.centro(c))) for c in coordenadas_hexagonos()}
    assert len(centros) == 19
