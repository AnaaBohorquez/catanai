"""El chat sin modelo de lenguaje: intenciones por palabras clave."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.api import PeticionChat
from app.services import chat

cliente = TestClient(app)


@pytest.fixture(scope="module")
def pantalla() -> dict:
    tablero = cliente.get("/api/v1/tableros/aleatorio?semilla=1").json()
    datos = cliente.post("/api/v1/recomendar", json={"tablero": tablero}).json()
    return {"tablero": tablero, "opciones": datos["opciones"]}


def _responder(pantalla: dict, pregunta: str) -> str:
    return chat._con_plantillas(PeticionChat(pregunta=pregunta, **pantalla))


def test_normalizar_quita_acentos_y_signos():
    assert chat.normalizar("¿Qué ESTRATEGIA sigo?") == " que estrategia sigo "


@pytest.mark.parametrize(
    "pregunta",
    ["¿Qué estrategia me conviene?", "que estrategia sigo", "¿Qué construyo primero?",
     "¿Cómo gano con esta?", "y después qué hago"],
)
def test_la_estrategia_se_reconoce_con_o_sin_acentos(pantalla, pregunta):
    texto = _responder(pantalla, pregunta)
    assert "Plan:" in texto
    assert pantalla["opciones"][0]["explicacion"]["titulo"] in texto


def test_nombrar_otra_familia_explica_esa(pantalla):
    otra = pantalla["opciones"][1]["explicacion"]["titulo"]
    palabra = {"Expansión": "Expansión", "Ciudades y desarrollo": "Ciudades",
               "Puerto y conversión": "Puerto"}.get(otra, otra)
    texto = _responder(pantalla, f"¿Cómo juego {palabra}?")
    assert texto.startswith(f"**{otra}**")


@pytest.mark.parametrize(
    "pregunta", ["¿Cuánto cuesta una ciudad?", "que necesito para la ciudad"]
)
def test_costos(pantalla, pregunta):
    texto = _responder(pantalla, pregunta)
    assert "2 trigo" in texto and "3 mineral" in texto


def test_costos_sin_recomendacion():
    texto = chat._con_plantillas(PeticionChat(pregunta="¿cuánto cuesta un camino?"))
    assert "1 madera" in texto


def test_probabilidad(pantalla):
    assert "5 de 36" in _responder(pantalla, "¿Qué probabilidad tiene el 8?")


def test_si_me_quitan_no_es_estrategia(pantalla):
    assert "Rival" in _responder(pantalla, "¿Qué hago si me quitan el vértice?")


def test_por_defecto_ofrece_preguntas(pantalla):
    texto = _responder(pantalla, "blablá")
    assert all(s in texto for s in chat.SUGERENCIAS_BASICAS)
