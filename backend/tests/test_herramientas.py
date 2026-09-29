"""Pruebas de las herramientas de "experto en Catan" del asistente."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from app.domain.reglas import leer_reglas
from app.domain.tablero import COSTOS, PIPS, RECURSOS
from app.main import app
from app.schemas.api import PeticionChat
from app.services.herramientas import DEFINICIONES, Herramientas

cliente = TestClient(app)


@pytest.fixture(scope="module")
def pantalla() -> dict:
    tablero = cliente.get("/api/v1/tableros/aleatorio?semilla=1").json()
    datos = cliente.post("/api/v1/recomendar", json={"tablero": tablero}).json()
    return {"tablero": tablero, "opciones": datos["opciones"]}


def _usar(pantalla: dict, nombre: str, **argumentos) -> tuple[dict, Herramientas]:
    herramientas = Herramientas(PeticionChat(pregunta="x", **pantalla))
    return json.loads(herramientas.ejecutar(nombre, json.dumps(argumentos))), herramientas


def _mano(**cartas) -> dict:
    return {r: cartas.get(r, 0) for r in RECURSOS}


def test_todas_las_herramientas_tienen_implementacion():
    for definicion in DEFINICIONES:
        assert hasattr(Herramientas, f"_{definicion['name']}"), definicion["name"]


def test_el_costo_sale_de_la_tabla_del_dominio(pantalla):
    salida, herramientas = _usar(pantalla, "costo_de_construccion", pieza="todas")
    assert {p: d["costo"] for p, d in salida.items()} == COSTOS
    assert salida["ciudad"]["puntos_de_victoria"] == 2
    assert herramientas.fuentes == {"reglas"}


def test_que_me_falta_para_una_ciudad(pantalla):
    salida, _ = _usar(pantalla, "que_me_falta", mano=_mano(trigo=2, mineral=1), pieza="ciudad")
    assert salida["alcanza_ya"] is False
    assert salida["faltan"] == {"mineral": 2}
    assert salida["puede_completar_cambiando"] is False


def test_que_me_falta_puede_completarse_cambiando_en_el_banco(pantalla, monkeypatch):
    # Sin puertos en la opción: todo cambio es 4:1 en el banco.
    monkeypatch.setattr(Herramientas, "_puertos_seleccionada", lambda self: set())
    salida, _ = _usar(pantalla, "que_me_falta", mano=_mano(madera=5), pieza="camino")
    assert salida["faltan"] == {"ladrillo": 1}
    assert salida["puede_completar_cambiando"] is True
    assert salida["cambios_sugeridos"] == ["entregar 4 madera por 1 carta (banco)"]


def test_que_me_falta_usa_el_puerto_2_1_si_lo_hay(pantalla, monkeypatch):
    monkeypatch.setattr(Herramientas, "_puertos_seleccionada", lambda self: {"trigo"})
    salida, _ = _usar(pantalla, "que_me_falta", mano=_mano(trigo=4), pieza="ciudad")
    # 2 trigo pagan la ciudad; los 2 que sobran dan 1 carta en el puerto 2:1.
    assert salida["faltan"] == {"mineral": 3}
    assert salida["cambios_sugeridos"] == ["entregar 2 trigo por 1 carta (puerto 2:1 de trigo)"]
    assert salida["puede_completar_cambiando"] is False


def test_una_mano_negativa_se_rechaza(pantalla):
    salida, _ = _usar(pantalla, "que_me_falta", mano=_mano(trigo=-1), pieza="ciudad")
    assert "error" in salida


def test_como_conseguir_usa_la_produccion_de_la_opcion(pantalla):
    salida, herramientas = _usar(pantalla, "como_conseguir", recurso="mineral")
    opcion = pantalla["opciones"][0]
    jugadores = opcion["variables"]["jugadores"]
    esperado = round(opcion["variables"]["pips_mineral"] / 36 * jugadores, 3)
    assert salida["cartas_por_ronda_produciendo"] == esperado
    cambios = salida["mejores_cambios"]
    assert cambios == sorted(cambios, key=lambda c: -c["cartas_conseguidas_por_ronda"])
    assert herramientas.fuentes == {"modelo"}


def test_plan_de_construccion_repite_las_variables_del_modelo(pantalla):
    salida, _ = _usar(pantalla, "plan_de_construccion")
    variables = pantalla["opciones"][0]["variables"]
    assert salida["rondas_estimadas_hasta"]["ciudad"] == round(variables["turnos_a_ciudad"], 1)


def test_probabilidad_de_un_8_es_5_de_36(pantalla):
    salida, _ = _usar(pantalla, "probabilidad_de_numero", numero=8)
    assert salida["combinaciones_de_36"] == PIPS[8] == 5
    assert salida["probabilidad"] == round(5 / 36, 4)


def test_el_7_se_explica_y_el_13_no_existe(pantalla):
    siete, _ = _usar(pantalla, "probabilidad_de_numero", numero=7)
    assert "ladrón" in siete["nota"]
    trece, _ = _usar(pantalla, "probabilidad_de_numero", numero=13)
    assert "error" in trece


def test_resumen_del_tablero_cuadra_con_los_58_pips(pantalla):
    salida, _ = _usar(pantalla, "resumen_del_tablero")
    assert sum(salida["pips_totales_por_recurso"].values()) == 58
    assert sum(salida["puertos"].values()) == 9


def test_resumen_del_tablero_devuelve_los_empates_juntos(pantalla, monkeypatch):
    empatados = {"madera": 9, "ladrillo": 9, "trigo": 16, "oveja": 14, "mineral": 10}
    monkeypatch.setattr(
        "app.services.herramientas.pips_por_recurso_del_tablero", lambda _: empatados
    )
    salida, _ = _usar(pantalla, "resumen_del_tablero")
    assert salida["mas_escasos"] == ["madera", "ladrillo"]
    assert salida["mas_abundantes"] == ["trigo"]


def test_las_instrucciones_prohiben_mostrar_ids_de_vertice():
    from app.services.chat import INSTRUCCIONES

    assert "Nunca muestres ids de vértice" in INSTRUCCIONES


def test_sin_opciones_las_herramientas_de_la_opcion_lo_dicen():
    herramientas = Herramientas(PeticionChat(pregunta="x"))
    assert "error" in json.loads(herramientas.ejecutar("plan_de_construccion", "{}"))
    salida = herramientas.ejecutar("como_conseguir", '{"recurso": "trigo"}')
    assert "error" in json.loads(salida)


# --- Coherencia entre la regla escrita y la tabla del código ---------------------

_PIEZA_EN_TEXTO = {
    "camino": "Camino",
    "poblado": "Poblado",
    "ciudad": "Ciudad",
    "carta_desarrollo": "Carta de desarrollo",
}


def test_la_regla_de_costos_coincide_con_la_tabla_del_codigo():
    """
    El chat cita `reglas.md`; el simulador y las herramientas usan `COSTOS`. Si alguien
    corrige uno y no el otro, esta prueba falla.
    """
    texto = next(r["texto"] for r in leer_reglas() if r["id"] == "costos")
    for pieza, nombre in _PIEZA_EN_TEXTO.items():
        tramo = re.search(rf"{nombre}:([^.]*)\.", texto)
        assert tramo, f"La regla de costos no menciona {nombre}"
        pares = re.findall(r"(\d+) (madera|ladrillo|trigo|oveja|mineral)", tramo.group(1))
        costo = {recurso: int(n) for n, recurso in pares}
        assert costo == COSTOS[pieza], pieza


# --- Estrategia -----------------------------------------------------------------


def test_explicar_estrategia_usa_la_familia_de_la_seleccionada(pantalla):
    salida, herramientas = _usar(pantalla, "explicar_estrategia", familia=None)
    primera = pantalla["opciones"][0]
    assert salida["opcion"] == 1
    assert salida["familia"] == primera["explicacion"]["titulo"]
    assert salida["plan"] and all("que" in paso for paso in salida["plan"])
    assert {c["variable"] for c in salida["por_que_es_de_esta_familia"]} >= {
        "par_camino", "trio_desarrollo", "puerto_alineado"
    }
    assert all(o["opcion"] != 1 for o in salida["otras_familias_en_pantalla"])
    assert herramientas.fuentes == {"modelo"}


def test_explicar_estrategia_de_otra_familia_usa_su_opcion(pantalla):
    otra = pantalla["opciones"][1]
    salida, _ = _usar(pantalla, "explicar_estrategia", familia=otra["estrategia"])
    assert salida["opcion"] == 2


def test_explicar_estrategia_sin_opcion_de_esa_familia(pantalla):
    en_pantalla = {o["estrategia"] for o in pantalla["opciones"]}
    ausente = next(f for f in ("expansion", "ciudades", "puerto", "desequilibrada")
                   if f not in en_pantalla)
    salida, _ = _usar(pantalla, "explicar_estrategia", familia=ausente)
    assert "plan" not in salida
    assert "Ninguna" in salida["nota"]


def test_explicar_estrategia_no_muestra_ids(pantalla):
    salida, _ = _usar(pantalla, "explicar_estrategia", familia=None)
    texto = json.dumps(salida, ensure_ascii=False)
    assert not re.search(r"-?\d+,-?\d+\|", texto)


def test_el_plan_sigue_la_prioridad_de_la_familia(pantalla):
    from app.services.herramientas import PRIORIDAD

    for i, opcion in enumerate(pantalla["opciones"]):
        herramientas = Herramientas(PeticionChat(pregunta="x", elegida=i, **pantalla))
        salida = herramientas._explicar_estrategia(None)
        assert len(salida["plan"]) == len(PRIORIDAD[opcion["estrategia"]])
