"""Hacia dónde crecer después de la colocación inicial."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from app.domain.expansion import (
    destinos_de_expansion,
    es_legal,
    puntuar_destino,
    rutas_desde,
    verificar_expansion,
)
from app.domain.simulador import TOPOLOGIA, parejas_candidatas
from app.domain.tablero import generar_tablero, pips_del_vertice
from app.main import app
from app.schemas.api import PeticionChat
from app.services import chat
from app.services.herramientas import Herramientas

cliente = TestClient(app)
_ID_VERTICE = re.compile(r"-?\d+,-?\d+\|")


@pytest.fixture(scope="module")
def tablero() -> dict:
    return generar_tablero(semilla=3)


@pytest.fixture(scope="module")
def propios(tablero) -> list:
    return list(parejas_candidatas(tablero)[0])


def test_los_destinos_son_legales_y_sus_rutas_validas(tablero, propios):
    destinos = destinos_de_expansion(tablero, propios, [])
    assert len(destinos) == 3
    verificar_expansion(destinos, propios, [])
    puntajes = [d["puntaje"] for d in destinos]
    assert puntajes == sorted(puntajes, reverse=True)


def test_ninguna_ruta_cruza_un_poblado_rival(tablero, propios):
    # Un rival justo al lado de cada poblado propio corta esas salidas.
    rivales = [
        next(
            v for v in TOPOLOGIA.adyacentes[p]
            if all(v not in TOPOLOGIA.adyacentes[q] and v != q for q in propios if q != p)
        )
        for p in propios
    ]
    rutas = rutas_desde(propios, rivales, max_caminos=3)
    assert not any(set(ruta[1:]) & set(rivales) for ruta in rutas.values())
    destinos = destinos_de_expansion(tablero, propios, rivales)
    verificar_expansion(destinos, propios, rivales)


def test_un_destino_necesita_al_menos_dos_caminos(tablero, propios):
    for d in destinos_de_expansion(tablero, propios, [], cuantos=20):
        assert d["caminos"] >= 2
        assert es_legal(d["vertice"], propios)


def test_la_formula_suma_sus_terminos(tablero, propios):
    rutas = rutas_desde(propios, [], max_caminos=3)
    vertice, ruta = next((v, r) for v, r in rutas.items() if len(r) == 4)
    d = puntuar_destino(vertice, ruta, propios, [], tablero)
    assert d["desglose"]["pips"] == pips_del_vertice(vertice, tablero)
    assert d["desglose"]["caminos_extra"] == -2.0  # 3 caminos: uno más que el mínimo
    assert d["puntaje"] == pytest.approx(sum(d["desglose"].values()))


def test_un_rival_cerca_resta(tablero, propios):
    rutas = rutas_desde(propios, [], max_caminos=2)
    vertice, ruta = next((v, r) for v, r in rutas.items() if len(r) == 3)
    rival = next(
        v for v in TOPOLOGIA.adyacentes[vertice] if v not in ruta and v not in propios
    )
    d = puntuar_destino(vertice, ruta, propios, [rival], tablero)
    assert d["riesgo_rival"] and d["desglose"]["rival_cerca"] == -2.0


# --- API y chat -----------------------------------------------------------------


@pytest.fixture(scope="module")
def pantalla() -> dict:
    t = cliente.get("/api/v1/tableros/aleatorio?semilla=1").json()
    opcion = cliente.post("/api/v1/recomendar", json={"tablero": t}).json()["opciones"][0]
    return {"tablero": t, "propios": opcion["vertices"]}


def test_el_endpoint_devuelve_destinos_con_letra(pantalla):
    r = cliente.post("/api/v1/expansion", json=pantalla)
    assert r.status_code == 200
    destinos = r.json()["destinos"]
    assert [d["letra"] for d in destinos] == ["A", "B", "C"]
    assert all(d["ruta"][0] in pantalla["propios"] for d in destinos)
    assert all(d["razones"] for d in destinos)


def test_con_dos_poblados_el_estado_dice_colocacion_completa(pantalla):
    peticion = PeticionChat(pregunta="x", **pantalla)
    texto = chat.estado_en_texto(peticion)
    assert "partida en curso: 2 poblados y 0 ciudades" in texto
    assert "tus poblados" in texto
    assert not _ID_VERTICE.search(texto)


def test_la_herramienta_devuelve_destinos_sin_ids(pantalla):
    h = Herramientas(PeticionChat(pregunta="x", **pantalla))
    salida = h.ejecutar("hacia_donde_expandir", "{}")
    assert not _ID_VERTICE.search(salida)
    assert h.destinos and len(h.destinos) == 3


def test_las_herramientas_de_opciones_redirigen_en_partida(pantalla):
    h = Herramientas(PeticionChat(pregunta="x", **pantalla))
    salida = h.ejecutar("explicar_estrategia", '{"familia": null}')
    assert "mi_produccion" in salida and "hacia_donde_expandir" in salida


def test_en_partida_el_plan_usa_tus_piezas(pantalla):
    h = Herramientas(PeticionChat(pregunta="x", **pantalla))
    salida = json.loads(h.ejecutar("plan_de_construccion", "{}"))
    assert salida["tus_piezas"] == {"poblados": 2, "ciudades": 0}
    piezas = {"camino", "poblado", "ciudad", "carta_desarrollo"}
    assert set(salida["rondas_estimadas_hasta"]) == piezas


@pytest.mark.parametrize(
    "pregunta",
    ["¿Hacia dónde crezco?", "¿cómo sigo mi estrategia?", "hacia donde tiendo mis caminos"],
)
def test_el_modo_basico_responde_con_los_destinos(pantalla, pregunta):
    r = chat.responder(PeticionChat(pregunta=pregunta, **pantalla))
    assert r.fuente == "plantillas"
    assert "### Destino A" in r.texto
    assert r.destinos and r.destinos[0].letra == "A"



# --- Partida en curso -------------------------------------------------------------


def test_mi_produccion_cuenta_doble_las_ciudades(pantalla):
    poblado, ciudad = pantalla["propios"]
    con_ciudad = Herramientas(PeticionChat(pregunta="x", tablero=pantalla["tablero"],
                                           propios=[poblado], ciudades=[ciudad]))
    sin_ciudad = Herramientas(PeticionChat(pregunta="x", **pantalla))
    a = json.loads(con_ciudad.ejecutar("mi_produccion", "{}"))
    b = json.loads(sin_ciudad.ejecutar("mi_produccion", "{}"))
    assert sum(a["pips_por_recurso"].values()) > sum(b["pips_por_recurso"].values())
    assert a["piezas"] == {"poblados": 1, "ciudades": 1}
    assert a["quedan"] == {"poblados": 4, "ciudades": 3}
    assert not _ID_VERTICE.search(con_ciudad.salidas[-1])


def test_la_expansion_parte_tambien_de_las_ciudades(pantalla):
    _, ciudad = pantalla["propios"]
    r = cliente.post("/api/v1/expansion", json={
        "tablero": pantalla["tablero"], "propios": [], "ciudades": [ciudad],
    })
    assert r.status_code == 200
    assert all(d["ruta"][0] == ciudad for d in r.json()["destinos"])


def test_mas_de_dos_poblados_propios(tablero, propios):
    tercero = destinos_de_expansion(tablero, propios, [])[0]["vertice"]
    destinos = destinos_de_expansion(tablero, [*propios, tercero], [])
    verificar_expansion(destinos, [*propios, tercero], [])


@pytest.mark.parametrize("pregunta", ["¿Qué construyo ahora?", "¿Qué hago ahora?"])
def test_en_partida_el_modo_basico_da_el_plan(pantalla, pregunta):
    r = chat.responder(PeticionChat(pregunta=pregunta, **pantalla))
    assert r.texto.startswith("### Tu partida · 2 poblados · 0 ciudades")
    assert "**Lo que puedes construir antes**" in r.texto


def test_en_partida_ya_no_manda_a_recomendar(pantalla):
    r = chat.responder(PeticionChat(pregunta="hola", **pantalla))
    assert "Recomendar" not in r.texto
