"""
Pruebas del estado de colocación en el chat: marcas del tablero, referencias
visibles ("opción N, poblado K") y ningún id interno a la vista del modelo.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from app.domain.simulador import TOPOLOGIA
from app.main import app
from app.schemas.api import PeticionChat
from app.services import chat
from app.services.herramientas import Herramientas
from app.services.serializers import id_vertice, vertice_desde_id

cliente = TestClient(app)

#: Un id de vértice: tres coordenadas axiales separadas por barras.
_ID_VERTICE = re.compile(r"-?\d+,-?\d+\|")


@pytest.fixture(scope="module")
def pantalla() -> dict:
    tablero = cliente.get("/api/v1/tableros/aleatorio?semilla=1").json()
    datos = cliente.post("/api/v1/recomendar", json={"tablero": tablero}).json()
    return {"tablero": tablero, "opciones": datos["opciones"]}


def _herramientas(pantalla: dict, **estado) -> Herramientas:
    return Herramientas(PeticionChat(pregunta="x", **pantalla, **estado))


def _usar(herramientas: Herramientas, nombre: str, **argumentos) -> dict:
    return json.loads(herramientas.ejecutar(nombre, json.dumps(argumentos)))


def _sin_vecinos(a: str, b: str) -> bool:
    va, vb = vertice_desde_id(a), vertice_desde_id(b)
    return va != vb and vb not in TOPOLOGIA.adyacentes[va]


# --- Referencias visibles -------------------------------------------------------


def test_ocupar_por_referencia_recalcula_y_devuelve_el_estado(pantalla):
    h = _herramientas(pantalla)
    tomado = pantalla["opciones"][0]["vertices"][0]

    salida = _usar(h, "solicitar_recomendacion",
                   ocupar=[{"opcion": 1, "poblado": 1}], mio=None, jugadores=None)

    assert salida["momento"] == "primera colocación"
    assert h.estado_nuevo.ocupados == [tomado]
    # Ninguna opción nueva usa el vértice tomado ni uno de sus vecinos.
    for opcion in h.opciones_nuevas:
        assert all(_sin_vecinos(tomado, v) for v in opcion.vertices)


def test_mio_por_referencia_pasa_a_la_segunda_colocacion(pantalla):
    h = _herramientas(pantalla)
    mio = pantalla["opciones"][1]["vertices"][0]

    salida = _usar(h, "solicitar_recomendacion",
                   ocupar=[], mio={"opcion": 2, "poblado": 1}, jugadores=None)

    assert salida["momento"] == "segunda colocación"
    assert h.estado_nuevo.mio == mio
    assert all(mio in o.vertices for o in h.opciones_nuevas)


def test_una_referencia_invalida_explica_cuales_son_validas(pantalla):
    h = _herramientas(pantalla)
    salida = _usar(h, "solicitar_recomendacion",
                   ocupar=[{"opcion": 9, "poblado": 3}], mio=None, jugadores=None)
    assert "Hay 3 opciones" in salida["error"]
    assert h.opciones_nuevas is None


def test_el_estado_marcado_se_conserva_al_sumar_cambios(pantalla):
    rival = pantalla["opciones"][2]["vertices"][1]
    h = _herramientas(pantalla, ocupados=[rival])
    _usar(h, "solicitar_recomendacion",
          ocupar=[{"opcion": 1, "poblado": 1}], mio=None, jugadores=None)
    assert rival in h.estado_nuevo.ocupados


def test_un_rival_no_puede_tomar_el_poblado_del_usuario(pantalla):
    mio = pantalla["opciones"][0]["vertices"][0]
    h = _herramientas(pantalla, mio=mio)
    salida = _usar(h, "solicitar_recomendacion",
                   ocupar=[{"opcion": 1, "poblado": 1}], mio=None, jugadores=None)
    assert "error" in salida


def test_la_regla_de_distancia_bloquea_un_rival_pegado_a_otro(pantalla):
    rival = pantalla["opciones"][0]["vertices"][0]
    vecino = next(iter(TOPOLOGIA.adyacentes[vertice_desde_id(rival)]))
    h = _herramientas(pantalla, ocupados=[rival])
    assert h._bloqueado(id_vertice(vecino), [rival], None)


# --- Estado del tablero ---------------------------------------------------------


def test_ver_estado_cuenta_rivales_y_libres(pantalla):
    rival = pantalla["opciones"][0]["vertices"][0]
    h = _herramientas(pantalla, ocupados=[rival])
    salida = _usar(h, "ver_estado_del_tablero")
    vecinos = len(TOPOLOGIA.adyacentes[vertice_desde_id(rival)])
    assert salida["rivales_marcados"] == 1
    assert salida["vertices_libres_legales"] == 54 - 1 - vecinos
    assert salida["tu_poblado"] == "aún no colocas"


def test_el_contexto_de_cada_pregunta_lleva_el_estado_sin_ids(pantalla):
    mio = pantalla["opciones"][0]["vertices"][0]
    peticion = PeticionChat(pregunta="x", **pantalla, mio=mio, ocupados=[])
    texto = chat.estado_en_texto(peticion)
    assert "segunda colocación" in texto
    assert "tu primer poblado" in texto
    assert not _ID_VERTICE.search(texto)


def test_ninguna_herramienta_muestra_ids(pantalla):
    rival = pantalla["opciones"][2]["vertices"][1]
    h = _herramientas(pantalla, ocupados=[rival])
    _usar(h, "ver_resultados_actuales")
    _usar(h, "comparar_opciones", a=1, b=2)
    _usar(h, "ver_estado_del_tablero")
    _usar(h, "solicitar_recomendacion",
          ocupar=[{"opcion": 1, "poblado": 1}], mio=None, jugadores=None)
    for salida in h.salidas:
        assert not _ID_VERTICE.search(salida), salida[:200]


def test_la_plantilla_de_me_quitan_indica_marcar_el_rival(pantalla):
    cuerpo = {"pregunta": "¿Y si me quitan un vértice?", **pantalla}
    r = cliente.post("/api/v1/chat", json=cuerpo)
    assert "Rival" in r.json()["texto"]
    assert "siguiente versión" not in r.json()["texto"]
