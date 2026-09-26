"""El endpoint central: dado un tablero, dónde colocar."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.api import PeticionRecomendar, RespuestaRecomendar
from app.services.recomendacion import ModeloNoDisponible, calcular

router = APIRouter(tags=["recomendaciones"])


@router.post(
    "/recomendar",
    response_model=RespuestaRecomendar,
    summary="Recomienda dónde colocar los poblados iniciales",
)
def recomendaciones(peticion: PeticionRecomendar) -> RespuestaRecomendar:
    """
    Devuelve las mejores opciones de colocación para este tablero.

    Si no se pasa ``mio``, busca **parejas** de poblados: es la primera colocación.
    Si se pasa, busca el mejor **compañero** para ese vértice, que es lo que hace
    falta en la segunda colocación, cuando entre tu primer poblado y el segundo
    ya jugaron los demás y pueden haberte quitado el sitio.

    Las opciones se devuelven de familias de estrategia distintas a propósito:
    tres opciones de expansión no ayudan a decidir, tres formas de jugar sí.
    """
    # El cálculo vive en services/recomendacion.py para que el chat use el mismo;
    # aquí solo se traduce la falta del modelo a un 503.
    try:
        return calcular(peticion)
    except ModeloNoDisponible as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El modelo no está cargado.",
        ) from error
