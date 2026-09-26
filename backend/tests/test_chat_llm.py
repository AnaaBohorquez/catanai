"""
Pruebas del chat con LLM y herramientas, sin red.

Un cliente simulado reproduce la forma de las respuestas de la Responses API
(items ``reasoning``, ``function_call`` y ``message``, ``status`` y ``usage``) con
un guion fijo, así que se prueba el bucle, el verificador y los límites sin gastar
tokens.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import ajustes
from app.domain import reglas
from app.main import app
from app.schemas.api import PeticionChat
from app.services import chat, consumo
from app.services.herramientas import Herramientas

cliente_http = TestClient(app)


# --- Cliente simulado ----------------------------------------------------------


def _uso(entrada: int = 500, salida: int = 80) -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=entrada,
        output_tokens=salida,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=40),
    )


def llamada(nombre: str, argumentos: dict, id_: str = "c1") -> SimpleNamespace:
    return SimpleNamespace(type="function_call", name=nombre, arguments=json.dumps(argumentos),
                           call_id=id_)


def razonamiento() -> SimpleNamespace:
    return SimpleNamespace(type="reasoning", id="r1")


def respuesta(*items, texto: str = "", status: str = "completed") -> SimpleNamespace:
    salida = list(items) or [SimpleNamespace(type="message")]
    return SimpleNamespace(status=status, output=salida, output_text=texto, usage=_uso())


class ClienteSimulado:
    """Devuelve las respuestas del guion en orden y guarda lo que recibió."""

    def __init__(self, guion: list[SimpleNamespace]) -> None:
        self.guion = list(guion)
        self.peticiones: list[dict] = []
        self.responses = self

    def create(self, **kwargs):
        # Copia de la entrada: el bucle sigue agregándole items después.
        self.peticiones.append({**kwargs, "input": list(kwargs["input"])})
        return self.guion.pop(0)


@pytest.fixture
def con_llm(monkeypatch):
    """Activa el modo LLM con un cliente simulado; devuelve una función para fijar el guion."""
    monkeypatch.setattr(ajustes, "openai_api_key", "clave-de-prueba")
    estado: dict = {}

    def usar(guion: list[SimpleNamespace]) -> ClienteSimulado:
        estado["cliente"] = ClienteSimulado(guion)
        monkeypatch.setattr(chat, "_crear_cliente", lambda: estado["cliente"])
        return estado["cliente"]

    return usar


@pytest.fixture(scope="module")
def pantalla() -> dict:
    """Un tablero fijo y sus opciones calculadas, como los tendría el frontend."""
    tablero = cliente_http.get("/api/v1/tableros/aleatorio?semilla=1").json()
    datos = cliente_http.post("/api/v1/recomendar", json={"tablero": tablero}).json()
    return {"tablero": tablero, "opciones": datos["opciones"]}


def _peticion(pantalla: dict, pregunta: str, **extra) -> PeticionChat:
    return PeticionChat(pregunta=pregunta, **pantalla, **extra)


# --- El bucle -------------------------------------------------------------------


def test_el_bucle_ejecuta_la_herramienta_y_devuelve_el_razonamiento(con_llm, pantalla):
    puntos = pantalla["opciones"][0]["prediccion"]
    simulado = con_llm([
        respuesta(razonamiento(), llamada("ver_resultados_actuales", {})),
        respuesta(texto=f"La **opción 1** estima {puntos:.1f} puntos en la simulación."),
    ])

    r = chat.responder(_peticion(pantalla, "¿Por qué la 1?"))

    assert r.fuente == "modelo_de_lenguaje"
    assert r.fuentes == ["modelo"]
    segunda = simulado.peticiones[1]["input"]
    # Los mensajes son dicts; los items que devolvió el modelo, objetos con `type`.
    tipos = [i.get("type") if isinstance(i, dict) else i.type for i in segunda]
    assert "reasoning" in tipos and "function_call" in tipos
    salida = next(
        i for i in segunda if isinstance(i, dict) and i.get("type") == "function_call_output"
    )
    assert salida["call_id"] == "c1"
    assert str(puntos) in salida["output"]


def test_una_cifra_inventada_se_reintenta_y_luego_cae_a_plantillas(
    con_llm, pantalla, consumo_aislado
):
    con_llm([
        respuesta(llamada("ver_resultados_actuales", {})),
        respuesta(texto="La opción 1 estima 99.9 puntos."),
        respuesta(texto="Insisto: 88.8 puntos."),
    ])

    r = chat.responder(_peticion(pantalla, "¿Por qué la 1?"))

    assert r.fuente == "plantillas"
    assert consumo_aislado[-1]["motivo"] == "verificador"


def test_el_reintento_puede_corregir_la_cifra(con_llm, pantalla):
    puntos = pantalla["opciones"][0]["prediccion"]
    simulado = con_llm([
        respuesta(llamada("ver_resultados_actuales", {})),
        respuesta(texto="Estima 99.9 puntos."),
        respuesta(texto=f"Estima {puntos} puntos."),
    ])

    r = chat.responder(_peticion(pantalla, "¿Por qué la 1?"))

    assert r.fuente == "modelo_de_lenguaje"
    ultima = simulado.peticiones[-1]["input"][-1]
    assert "Revisión automática" in ultima["content"]


def test_una_respuesta_incompleta_cae_a_plantillas(con_llm, pantalla, consumo_aislado):
    con_llm([respuesta(status="incomplete")])

    r = chat.responder(_peticion(pantalla, "¿Por qué la 1?"))

    assert r.fuente == "plantillas"
    assert consumo_aislado[-1]["motivo"] == "incompleta"


def test_un_error_de_red_cae_a_plantillas(monkeypatch, pantalla, consumo_aislado):
    monkeypatch.setattr(ajustes, "openai_api_key", "clave-de-prueba")

    def falla():
        raise ConnectionError("sin red")

    monkeypatch.setattr(chat, "_crear_cliente", falla)
    r = chat.responder(_peticion(pantalla, "¿Por qué la 1?"))
    assert r.fuente == "plantillas"
    assert consumo_aislado[-1]["motivo"] == "error:ConnectionError"


def test_solicitar_recomendacion_devuelve_opciones_nuevas(con_llm, pantalla):
    tomado = pantalla["opciones"][0]["vertices"][0]
    con_llm([
        respuesta(llamada("solicitar_recomendacion", {"ocupados": [tomado], "mio": None,
                                                      "jugadores": None})),
        respuesta(texto="Recalculé sin ese vértice: mira las opciones nuevas en el tablero."),
    ])

    r = chat.responder(_peticion(pantalla, "¿Y si me quitan el primer vértice de la opción 1?"))

    assert r.opciones_nuevas
    assert all(tomado not in o.vertices for o in r.opciones_nuevas)
    assert r.fuentes == ["modelo"]


def test_consejo_general_se_etiqueta(con_llm, pantalla):
    con_llm([respuesta(texto="Consejo general: habla con los demás antes de comerciar.")])
    r = chat.responder(_peticion(pantalla, "¿Algún truco para negociar?"))
    assert r.fuentes == ["general"]


def test_el_uso_se_cobra_y_se_anota(con_llm, pantalla, consumo_aislado):
    con_llm([respuesta(texto="Consejo general: sin cifras.")])
    chat.responder(_peticion(pantalla, "hola"))
    evento = consumo_aislado[-1]
    assert evento["resultado"] == "llm"
    assert evento["tokens"]["entrada"] == 500
    assert evento["usd"] > 0
    assert consumo.presupuesto.gastado > 0


# --- Verificador ---------------------------------------------------------------


def test_el_verificador_tolera_el_redondeo_y_el_signo():
    salidas = ['{"puntos_estimados": 8.58, "diferencia_puntos_estimados": -1.24}']
    texto = "Estima 8.6 puntos, 1.2 pts menos que la otra."
    assert chat.cifras_sin_respaldo(texto, salidas) == []
    assert chat.cifras_sin_respaldo("Estima 9.5 puntos.", salidas) == ["9.5"]
    assert chat.cifras_sin_respaldo("Sin cifras con unidad: la opción 2.", salidas) == []


# --- Herramientas --------------------------------------------------------------


def test_las_reglas_sin_verificar_no_se_devuelven(pantalla):
    herramientas = Herramientas(_peticion(pantalla, "x"))
    tema = json.dumps({"tema": "costo de una ciudad"})
    salida = json.loads(herramientas.ejecutar("consultar_reglas", tema))
    assert salida["reglas"] == []
    assert "reglas" not in herramientas.fuentes


def test_las_reglas_verificadas_si_se_devuelven(monkeypatch, pantalla):
    todas = reglas.leer_reglas()
    verificadas = tuple({**r, "verificado": True} for r in todas if r["id"] == "costos")
    monkeypatch.setattr("app.services.herramientas.reglas_verificadas", lambda: verificadas)
    herramientas = Herramientas(_peticion(pantalla, "x"))
    tema = json.dumps({"tema": "¿cuánto cuesta una ciudad?"})
    salida = json.loads(herramientas.ejecutar("consultar_reglas", tema))
    assert salida["reglas"][0]["id"] == "costos"
    assert "reglas" in herramientas.fuentes


def test_comparar_calcula_la_diferencia(pantalla):
    herramientas = Herramientas(_peticion(pantalla, "x"))
    salida = json.loads(herramientas.ejecutar("comparar_opciones", '{"a": 1, "b": 2}'))
    uno, dos = (o["prediccion"] for o in pantalla["opciones"][:2])
    assert salida["diferencia_puntos_estimados"] == round(uno - dos, 2)


def test_una_herramienta_desconocida_no_rompe_nada(pantalla):
    herramientas = Herramientas(_peticion(pantalla, "x"))
    assert "desconocida" in herramientas.ejecutar("borrar_todo", "{}")


# --- Límites -------------------------------------------------------------------


def test_el_limite_por_ip_responde_429(monkeypatch):
    monkeypatch.setattr(consumo, "limitador", consumo.LimitadorPorIp(2, 600))
    cuerpo = {"pregunta": "hola"}
    assert cliente_http.post("/api/v1/chat", json=cuerpo).status_code == 200
    assert cliente_http.post("/api/v1/chat", json=cuerpo).status_code == 200
    assert cliente_http.post("/api/v1/chat", json=cuerpo).status_code == 429


def test_sin_presupuesto_se_usan_plantillas_y_health_lo_dice(monkeypatch, pantalla):
    monkeypatch.setattr(ajustes, "openai_api_key", "clave-de-prueba")
    agotado = consumo.Presupuesto(0.0)
    monkeypatch.setattr(consumo, "presupuesto", agotado)

    r = chat.responder(_peticion(pantalla, "¿Por qué la 1?"))

    assert r.fuente == "plantillas"
    assert cliente_http.get("/api/v1/health").json()["chat_con_llm"] is False
