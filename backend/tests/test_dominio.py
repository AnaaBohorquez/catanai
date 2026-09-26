"""Pruebas del dominio: las reglas del juego que no pueden romperse."""

from __future__ import annotations

import pytest

from app.domain.simulador import parejas_candidatas, simular_pareja
from app.domain.tablero import (
    generar_tablero,
    todas_las_aristas,
    todos_los_vertices,
    verificar_tablero,
)
from app.domain.variables import variables_de_parejas, verificar_variables


def test_topologia_del_tablero():
    """El tablero del juego base tiene 19 hexágonos, 54 vértices y 72 aristas."""
    assert len(generar_tablero(semilla=0)["hexagonos"]) == 19
    assert len(todos_los_vertices()) == 54
    assert len(todas_las_aristas()) == 72


@pytest.mark.parametrize("semilla", range(12))
def test_tableros_generados_son_validos(semilla: int):
    verificar_tablero(generar_tablero(semilla=semilla))


def test_los_pips_suman_58():
    """Dato fijo del juego base: si cambia, algo se rompió en el generador."""
    assert sum(generar_tablero(semilla=7)["pips"].values()) == 58


def test_las_parejas_respetan_la_distancia_minima():
    """Dos poblados propios nunca pueden ser adyacentes."""
    from app.domain.variables import _ADYACENTES

    tablero = generar_tablero(semilla=3)
    for a, b in parejas_candidatas(tablero):
        assert b not in _ADYACENTES[a]


def test_los_ocupados_bloquean_a_sus_vecinos():
    from app.domain.variables import _ADYACENTES

    tablero = generar_tablero(semilla=5)
    ocupado = todos_los_vertices()[10]
    prohibidos = {ocupado} | set(_ADYACENTES[ocupado])
    for a, b in parejas_candidatas(tablero, ocupados={ocupado}):
        assert a not in prohibidos and b not in prohibidos


def test_las_variables_son_coherentes():
    tablero = generar_tablero(semilla=11)
    parejas = parejas_candidatas(tablero)[:40]
    verificar_variables(tablero, parejas)


def test_la_simulacion_es_reproducible():
    tablero = generar_tablero(semilla=2)
    a, b = parejas_candidatas(tablero)[0]
    primera = simular_pareja(tablero, a, b, partidas=15, semilla=99)
    segunda = simular_pareja(tablero, a, b, partidas=15, semilla=99)
    assert primera == segunda


def test_ninguna_variable_es_constante():
    """Una variable que nunca cambia no puede explicar por qué una pareja es mejor."""
    from app.domain.variables import verificar_variabilidad

    verificar_variabilidad(tableros=8)
