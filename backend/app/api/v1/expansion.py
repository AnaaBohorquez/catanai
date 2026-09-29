"""Después de la colocación inicial: hacia dónde crecer."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import PeticionExpansion, RespuestaExpansion
from app.services.expansion import calcular

router = APIRouter(tags=["expansion"])


@router.post(
    "/expansion",
    response_model=RespuestaExpansion,
    summary="Sugiere dónde poner el siguiente poblado",
)
def expansion(peticion: PeticionExpansion) -> RespuestaExpansion:
    """
    Con tus poblados colocados, los mejores vértices para el siguiente (A, B y C),
    a los que puedes llegar con caminos sin cruzar poblados rivales.

    El puntaje es una fórmula a la vista (pips, recursos nuevos, puerto, caminos,
    rivales cerca), no el modelo de regresión, que se entrenó para la colocación
    inicial.
    """
    return calcular(peticion)
