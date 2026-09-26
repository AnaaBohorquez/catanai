"""Generación y validación de tableros."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.domain.tablero import generar_tablero
from app.schemas.api import Tablero, TableroConAvisos
from app.services.serializers import (
    avisos_del_tablero,
    tablero_a_api,
    tablero_desde_api,
)

router = APIRouter(prefix="/tableros", tags=["tableros"])


@router.get("/aleatorio", response_model=Tablero, summary="Genera un tablero válido")
def aleatorio(
    semilla: int | None = Query(default=None, description="Fija el azar para reproducir"),
) -> Tablero:
    """
    Un tablero del juego base, listo para probar la app sin capturar nada.

    Respeta el reparto de terrenos y fichas, y evita dejar dos números rojos
    (el 6 y el 8) en hexágonos adyacentes, como recomienda el reglamento.
    """
    tablero = generar_tablero(semilla=semilla)
    return Tablero(**tablero_a_api(tablero), semilla=semilla)


@router.post("/validar", response_model=TableroConAvisos, summary="Revisa un tablero")
def validar(tablero: Tablero) -> TableroConAvisos:
    """
    Comprueba un tablero contra las reglas del juego base.

    Devuelve avisos en lugar de rechazarlo: el usuario puede estar a mitad de la
    captura, y bloquearlo ahí sería más molesto que útil.
    """
    dominio = tablero_desde_api(tablero.model_dump())
    return TableroConAvisos(
        tablero=Tablero(**tablero_a_api(dominio)),
        avisos=avisos_del_tablero(dominio),
    )
