"""
Reglas del juego verificadas, leídas de ``reglas.md``.

El asistente no responde reglas "de memoria": las consulta aquí. Solo cuentan las
entradas marcadas ``verificado: sí``, que son las que alguien comparó contra el
reglamento oficial.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

RUTA_REGLAS = Path(__file__).with_name("reglas.md")

#: Palabras que no ayudan a encontrar una regla.
_VACIAS = {
    "que", "qué", "cual", "cuál", "como", "cómo", "cuanto", "cuánto", "cuanta", "cuánta",
    "para", "por", "con", "una", "uno", "los", "las", "del", "sus", "hay", "puedo",
    "pasa", "sale", "regla", "reglas", "catan", "juego", "cuando", "cuándo", "tengo",
}


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para que 'ladrón' encuentre 'ladron'."""
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")


def leer_reglas(ruta: Path = RUTA_REGLAS) -> list[dict]:
    """
    Todas las entradas del archivo, verificadas o no.

    Returns
    -------
    list[dict]
        Una por entrada, con ``id``, ``temas``, ``fuente``, ``verificado`` y ``texto``.
    """
    entradas = []
    for bloque in re.split(r"^## ", ruta.read_text(encoding="utf-8"), flags=re.M)[1:]:
        lineas = bloque.strip().splitlines()
        campos = {"id": lineas[0].strip()}
        cuerpo = []
        for linea in lineas[1:]:
            clave, _, valor = linea.partition(":")
            if clave.strip() in {"temas", "fuente", "verificado"} and not cuerpo:
                campos[clave.strip()] = valor.strip()
            else:
                cuerpo.append(linea)
        campos["verificado"] = _normalizar(campos.get("verificado", "no")) in {"si", "sí"}
        campos["temas"] = [t.strip() for t in campos.get("temas", "").split(",") if t.strip()]
        campos["texto"] = " ".join(" ".join(cuerpo).split())
        entradas.append(campos)
    return entradas


@lru_cache
def reglas_verificadas() -> tuple[dict, ...]:
    """Solo las que se pueden citar. Se leen una vez por proceso."""
    return tuple(r for r in leer_reglas() if r["verificado"])


def buscar_reglas(
    tema: str, reglas: tuple[dict, ...] | list[dict], cuantas: int = 2
) -> list[dict]:
    """
    Las reglas que mejor responden a ``tema``, por coincidencia de palabras.

    Un tema de la entrada que aparezca en la pregunta pesa más que una palabra suelta
    del texto, porque los temas se escribieron justo para esto.
    """
    pregunta = _normalizar(tema)
    palabras = {
        p for p in re.findall(r"[a-z0-9:]+", pregunta) if len(p) > 2 and p not in _VACIAS
    }

    def puntaje(regla: dict) -> int:
        temas = [_normalizar(t) for t in regla["temas"]]
        texto = _normalizar(regla["texto"])
        exactos = sum(3 for t in temas if t in pregunta)
        sueltas = sum(2 for p in palabras if any(p in t for t in temas))
        en_texto = sum(1 for p in palabras if p in texto)
        return exactos + sueltas + en_texto

    con_puntaje = [(puntaje(r), r) for r in reglas]
    mejores = sorted((par for par in con_puntaje if par[0] > 0), key=lambda par: -par[0])
    return [r for _, r in mejores[:cuantas]]
