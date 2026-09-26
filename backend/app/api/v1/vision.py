"""Lectura del tablero a partir de una fotografía."""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.core.errors import ErrorDeDominio
from app.schemas.api import RespuestaVision
from app.services import vision as servicio

router = APIRouter(prefix="/vision", tags=["vision"])

TIPOS = {"image/jpeg", "image/png", "image/webp"}
LIMITE_MB = 12


@router.post(
    "/tablero",
    response_model=RespuestaVision,
    summary="Detecta el tablero a partir de una foto",
)
async def leer_tablero(foto: UploadFile = File(...)) -> RespuestaVision:
    """
    Lee una foto del tablero **vacío** y devuelve los terrenos y números detectados.

    La detección nunca se da por definitiva: la respuesta trae una confianza por
    hexágono para que la interfaz señale cuáles conviene revisar. El usuario
    confirma o corrige antes de calcular, así que un error de la visión es una
    corrección de dos clics y no una recomendación equivocada.
    """
    if foto.content_type not in TIPOS:
        raise ErrorDeDominio(
            "Formato de imagen no admitido",
            f"Se recibió {foto.content_type}; se admiten JPEG, PNG y WebP.",
        )

    contenido = await foto.read()
    if len(contenido) > LIMITE_MB * 1_000_000:
        raise ErrorDeDominio(f"La imagen supera los {LIMITE_MB} MB")

    return servicio.leer_tablero(contenido)
