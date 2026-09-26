"""Pruebas de cómo se eligen las opciones que ve el usuario."""

from __future__ import annotations

from app.services.recomendador import _elegir


def _elegir_familias(familias: list[str], cuantas: int = 3) -> list[int]:
    """Llama a ``_elegir`` con parejas ya ordenadas de mejor a peor."""
    nombres = dict(enumerate(sorted(set(familias))))
    grupo_de = {v: k for k, v in nombres.items()}
    grupos = [grupo_de[f] for f in familias]
    return _elegir(list(range(len(familias))), grupos, nombres, cuantas, diversificar=True)


def test_la_desequilibrada_no_entra_como_alternativa():
    elegidas = _elegir_familias(["expansion", "desequilibrada", "ciudades", "expansion"])
    assert elegidas == [0, 2, 3]


def test_la_desequilibrada_se_muestra_si_es_la_mejor():
    elegidas = _elegir_familias(["desequilibrada", "expansion", "ciudades"])
    assert elegidas == [0, 1, 2]


def test_se_completa_con_las_siguientes_mejores_de_otras_familias():
    elegidas = _elegir_familias(["expansion", "expansion", "desequilibrada", "expansion"])
    assert elegidas == [0, 1, 3]


def test_la_desequilibrada_entra_solo_si_no_queda_nada_mas():
    elegidas = _elegir_familias(["expansion", "desequilibrada", "desequilibrada"])
    assert elegidas == [0, 1, 2]
