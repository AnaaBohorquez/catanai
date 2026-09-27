"""
Pruebas de la lectura del tablero por foto, con imágenes sintéticas.

No hay fotos reales en el repositorio, así que se dibuja un tablero con OpenCV y se
pasa por la visión. Esto comprueba el contrato y la geometría en condiciones ideales;
NO dice nada de cómo funciona con fotos reales, que siguen sin calibrar.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.domain.puertos import (
    aristas_de_costa_en_orden,
    plantilla_de_puertos,
    verificar_puertos,
)
from app.domain.tablero import coordenadas_hexagonos, generar_tablero
from app.main import app
from app.services import vision

cliente = TestClient(app)

#: Un color representativo de cada terreno: el centro de su rango en `RANGOS`.
def _color_de(terreno: str) -> tuple[int, int, int]:
    rango = vision.RANGOS[terreno]
    hsv = np.uint8([[[sum(rango[c]) // 2 for c in ("h", "s", "v")]]])
    return tuple(int(x) for x in cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0])


def foto_sintetica(terrenos: dict, angulo: float = 0.0, lado: int = 60) -> bytes:
    """
    Un tablero dibujado sobre fondo negro (que la máscara de la visión descarta),
    con hexágonos de punta arriba y, si se pide, girado unos grados.
    """
    lienzo = np.zeros((900, 1000, 3), dtype=np.uint8)
    cx, cy = 500, 450
    giro = math.radians(angulo)
    for (q, r), terreno in terrenos.items():
        x, y = lado * math.sqrt(3) * (q + r / 2), lado * 1.5 * r
        esquinas = []
        for i in range(6):
            a = math.radians(60 * i - 90)
            px, py = x + lado * 0.98 * math.cos(a), y + lado * 0.98 * math.sin(a)
            esquinas.append((
                cx + px * math.cos(giro) - py * math.sin(giro),
                cy + px * math.sin(giro) + py * math.cos(giro),
            ))
        cv2.fillPoly(lienzo, [np.int32(esquinas)], _color_de(terreno))
    ok, datos = cv2.imencode(".png", lienzo)
    assert ok
    return datos.tobytes()


@pytest.fixture(scope="module")
def terrenos() -> dict:
    return generar_tablero(semilla=3)["terrenos"]


def _aciertos(respuesta, terrenos: dict) -> float:
    leidos = {(h.q, h.r): h.terreno for h in respuesta.tablero.hexagonos}
    return sum(leidos[c] == t for c, t in terrenos.items()) / len(terrenos)


# --- Contrato -------------------------------------------------------------------


def test_la_lectura_devuelve_19_hexagonos_y_la_plantilla_de_puertos(terrenos):
    respuesta = vision.leer_tablero(foto_sintetica(terrenos))
    assert len(respuesta.detecciones) == 19
    assert len(respuesta.tablero.puertos) == 9
    assert respuesta.puertos_confirmados is False
    assert all(h.numero is None for h in respuesta.tablero.hexagonos)
    assert any("plantilla" in a for a in respuesta.avisos)


def test_el_endpoint_acepta_una_foto(terrenos):
    r = cliente.post(
        "/api/v1/vision/tablero",
        files={"foto": ("tablero.png", foto_sintetica(terrenos), "image/png")},
    )
    assert r.status_code == 200
    assert len(r.json()["detecciones"]) == 19


def test_el_endpoint_rechaza_formatos_no_admitidos():
    archivo = {"foto": ("x.gif", b"GIF89a", "image/gif")}
    r = cliente.post("/api/v1/vision/tablero", files=archivo)
    assert r.status_code == 400


def test_el_endpoint_rechaza_fotos_de_mas_de_12_mb():
    grande = b"\0" * (12_000_001)
    r = cliente.post("/api/v1/vision/tablero", files={"foto": ("x.png", grande, "image/png")})
    assert r.status_code == 400


# --- Precisión en condiciones ideales (se mide y se reporta) ---------------------


@pytest.mark.parametrize("angulo", [0.0, 5.0])
def test_precision_en_imagen_sintetica(terrenos, angulo, capsys):
    """
    Con colores exactos de RANGOS y sin ruido, la visión debería acertar casi todo.
    Si no, el problema es la geometría (dónde busca cada hexágono), no el color.
    """
    precision = _aciertos(vision.leer_tablero(foto_sintetica(terrenos, angulo)), terrenos)
    with capsys.disabled():
        print(f"\n  visión sintética, giro {angulo}°: {precision:.0%} de terrenos acertados")
    assert precision >= 0.5


# --- Plantilla de puertos ---------------------------------------------------------


def test_la_costa_tiene_30_aristas_consecutivas():
    costa = aristas_de_costa_en_orden(coordenadas_hexagonos())
    assert len(costa) == 30
    # Recorrer la costa en orden: cada arista comparte un vértice con la siguiente.
    for a, b in zip(costa, costa[1:] + costa[:1], strict=True):
        assert a & b, "la costa no está en orden"


@pytest.mark.parametrize("giro", range(6))
def test_la_plantilla_es_valida_en_los_seis_giros(giro):
    hexagonos = coordenadas_hexagonos()
    puertos = plantilla_de_puertos(hexagonos, giro)
    assert verificar_puertos(puertos, hexagonos) == []


def test_validar_detecta_un_reparto_de_terrenos_o_fichas_incorrecto():
    tablero = cliente.get("/api/v1/tableros/aleatorio?semilla=1").json()
    assert cliente.post("/api/v1/tableros/validar", json=tablero).json()["avisos"] == []

    # Una colina pasa a campos: siguen siendo 19 hexágonos, pero el reparto no cuadra.
    colina = next(h for h in tablero["hexagonos"] if h["terreno"] == "colinas")
    colina["terreno"] = "campos"
    # Dos 12 y ningún 2: mismas 18 fichas y mismos pips, reparto distinto.
    dos = next(h for h in tablero["hexagonos"] if h["numero"] == 2)
    dos["numero"] = 12

    avisos = cliente.post("/api/v1/tableros/validar", json=tablero).json()["avisos"]
    assert any("reparto de terrenos" in a and "colinas 2 de 3" in a for a in avisos)
    assert any("fichas no son" in a for a in avisos)


def test_la_plantilla_coincide_con_el_tablero_de_referencia():
    """Posiciones medidas en la foto de principiantes (índices de arista de costa)."""
    hexagonos = coordenadas_hexagonos()
    costa = aristas_de_costa_en_orden(hexagonos)
    puertos = plantilla_de_puertos(hexagonos)
    posiciones = sorted(costa.index(a) for a in puertos)
    assert posiciones == [2, 5, 9, 12, 15, 19, 22, 25, 29]
    assert puertos[costa[5]] == "ladrillo"
    assert puertos[costa[15]] == "trigo"
    assert sorted(t for t in puertos.values() if t == "3:1") == ["3:1"] * 4


def test_verificar_puertos_detecta_un_reparto_incorrecto():
    hexagonos = coordenadas_hexagonos()
    puertos = {a: "3:1" for a in plantilla_de_puertos(hexagonos)}
    assert any("reparto" in a for a in verificar_puertos(puertos, hexagonos))
