"""Carga del modelo entrenado, una sola vez por proceso."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import ajustes
from app.services.recomendador import ESTRATEGIAS, cargar_modelo


@lru_cache
def paquete() -> dict | None:
    """
    El modelo y sus metadatos, o ``None`` si no se pudo cargar.

    Se devuelve ``None`` en vez de reventar para que la API pueda arrancar y
    responder en ``/health`` que está degradada, en lugar de no arrancar.
    """
    try:
        return cargar_modelo(ajustes.ruta_modelo)
    except Exception:  # noqa: BLE001 - el motivo se reporta en /health
        return None


def disponible() -> bool:
    return paquete() is not None


def estrategias() -> list[str]:
    return [ficha["nombre"] for ficha in ESTRATEGIAS.values()]
