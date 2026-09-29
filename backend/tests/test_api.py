"""Pruebas de la API: los contratos que consume el frontend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def test_salud():
    respuesta = cliente.get("/api/v1/health")
    assert respuesta.status_code == 200
    assert respuesta.json()["version"]


def test_tablero_aleatorio_es_reproducible():
    uno = cliente.get("/api/v1/tableros/aleatorio?semilla=42").json()
    otro = cliente.get("/api/v1/tableros/aleatorio?semilla=42").json()
    assert uno["hexagonos"] == otro["hexagonos"]
    assert len(uno["hexagonos"]) == 19
    assert len(uno["vertices"]) == 54
    assert len(uno["aristas"]) == 72


def test_validar_detecta_un_tablero_incompleto():
    tablero = cliente.get("/api/v1/tableros/aleatorio?semilla=1").json()
    tablero["hexagonos"] = tablero["hexagonos"][:10]
    respuesta = cliente.post("/api/v1/tableros/validar", json=tablero)
    assert respuesta.status_code == 200
    assert respuesta.json()["avisos"]


@pytest.mark.skipif(
    not cliente.get("/api/v1/health").json()["modelo_cargado"],
    reason="requiere modelos/colono.joblib",
)
def test_recomendar_devuelve_estrategias_distintas():
    tablero = cliente.get("/api/v1/tableros/aleatorio?semilla=42").json()
    respuesta = cliente.post("/api/v1/recomendar", json={
        "tablero": tablero, "jugadores": 4, "cuantas": 3,
    })
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["momento"] == "primera"
    assert len(datos["opciones"]) == 3
    # Las opciones se diversifican a propósito: tres de la misma familia no
    # ayudan a decidir.
    assert len({o["estrategia"] for o in datos["opciones"]}) > 1
    for opcion in datos["opciones"]:
        assert len(opcion["vertices"]) == 2
        assert opcion["explicacion"]["porque"]


@pytest.mark.skipif(
    not cliente.get("/api/v1/health").json()["modelo_cargado"],
    reason="requiere modelos/colono.joblib",
)
def test_segunda_colocacion_conserva_el_primer_poblado():
    tablero = cliente.get("/api/v1/tableros/aleatorio?semilla=42").json()
    mio = tablero["vertices"][20]["id"]
    respuesta = cliente.post("/api/v1/recomendar", json={
        "tablero": tablero, "mio": mio, "cuantas": 2,
    })
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["momento"] == "segunda"
    for opcion in datos["opciones"]:
        assert mio in opcion["vertices"]


def test_un_vertice_desconocido_da_error_claro():
    tablero = cliente.get("/api/v1/tableros/aleatorio?semilla=1").json()
    respuesta = cliente.post("/api/v1/recomendar", json={
        "tablero": tablero, "ocupados": ["no-existe"],
    })
    assert respuesta.status_code in (400, 503)


def test_el_chat_responde_sin_clave_de_llm():
    respuesta = cliente.post("/api/v1/chat", json={"pregunta": "¿por qué esa opción?"})
    assert respuesta.status_code == 200
    assert respuesta.json()["fuente"] == "plantillas"


@pytest.fixture(scope="module")
def recomendacion() -> dict:
    """Un tablero fijo con sus tres opciones calculadas, para preguntarle al chat."""
    tablero = cliente.get("/api/v1/tableros/aleatorio?semilla=1").json()
    datos = cliente.post("/api/v1/recomendar", json={"tablero": tablero}).json()
    return {"tablero": tablero, "opciones": datos["opciones"]}


def _preguntar(recomendacion: dict, pregunta: str, **extra) -> str:
    cuerpo = {"pregunta": pregunta, **recomendacion, **extra}
    respuesta = cliente.post("/api/v1/chat", json=cuerpo)
    assert respuesta.status_code == 200
    return respuesta.json()["texto"]


def test_el_chat_habla_de_la_opcion_elegida(recomendacion):
    titulo = recomendacion["opciones"][1]["explicacion"]["titulo"]
    texto = _preguntar(recomendacion, "¿Por qué esta opción?", elegida=1)
    assert "opción 2" in texto.lower()
    assert titulo in texto


def test_sin_elegida_el_chat_habla_de_la_opcion_1(recomendacion):
    titulo = recomendacion["opciones"][0]["explicacion"]["titulo"]
    texto = _preguntar(recomendacion, "¿Por qué esta opción?")
    assert "opción 1" in texto.lower()
    assert titulo in texto


def test_la_comparacion_usa_las_cifras_del_modelo(recomendacion):
    uno, dos = (o["prediccion"] for o in recomendacion["opciones"][:2])
    texto = _preguntar(recomendacion, "Compárala con la opción 1", elegida=1)
    assert f"{dos:.1f}" in texto
    assert f"{uno:.1f}" in texto


def test_una_elegida_fuera_de_rango_no_rompe_el_chat(recomendacion):
    texto = _preguntar(recomendacion, "¿Qué construyo primero?", elegida=5)
    assert "opción 3" in texto.lower()
