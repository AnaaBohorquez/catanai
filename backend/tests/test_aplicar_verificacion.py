"""El script que pasa la verificación de la página a reglas.md."""

from __future__ import annotations

from app.domain.reglas import RUTA_REGLAS, leer_reglas
from scripts.aplicar_verificacion import aplicar


def test_marca_verificada_y_corrige_sin_tocar_las_demas(tmp_path):
    original = RUTA_REGLAS.read_text(encoding="utf-8")
    nuevo, desconocidos = aplicar(original, [
        {"id": "costos", "estado": "correcta", "fuente": "Reglamento, p. 7"},
        {"id": "comercio", "estado": "corregida", "fuente": "Reglamento, p. 9",
         "texto": "Texto corregido del comercio."},
        {"id": "no-existe", "estado": "correcta", "fuente": "x"},
    ])
    assert desconocidos == ["no-existe"]
    ruta = tmp_path / "reglas.md"
    ruta.write_text(nuevo, encoding="utf-8")
    antes = {r["id"]: r for r in leer_reglas(RUTA_REGLAS)}
    despues = {r["id"]: r for r in leer_reglas(ruta)}
    assert despues["costos"]["verificado"] and despues["costos"]["fuente"] == "Reglamento, p. 7"
    assert despues["costos"]["texto"] == antes["costos"]["texto"]
    assert despues["comercio"]["texto"] == "Texto corregido del comercio."
    assert despues["comercio"]["temas"] == antes["comercio"]["temas"]
    otras = set(antes) - {"costos", "comercio"}
    assert all(despues[i] == antes[i] for i in otras)
    assert len(despues) == len(antes)
    # El archivo real no se tocó.
    assert RUTA_REGLAS.read_text(encoding="utf-8") == original
