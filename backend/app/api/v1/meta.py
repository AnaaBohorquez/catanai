"""Salud del servicio e información del modelo."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.api import InfoModelo, Salud
from app.services import consumo, modelo

VERSION = "0.1.0"

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=Salud, summary="Estado del servicio")
def salud() -> Salud:
    cargado = modelo.disponible()
    return Salud(
        estado="ok" if cargado else "degradado",
        version=VERSION,
        modelo_cargado=cargado,
        # Con clave rechazada o sin presupuesto, el chat responde con plantillas
        # aunque haya clave puesta: /health lo dice y el frontend lo avisa.
        chat_con_llm=consumo.motivo_sin_llm() is None,
        chat_motivo=consumo.motivo_sin_llm(),
    )


@router.get("/modelo", response_model=InfoModelo, summary="Metadatos del modelo")
def info_modelo() -> InfoModelo:
    paquete = modelo.paquete()
    if paquete is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El modelo no está cargado. Genera backend/modelos/colono.joblib con el notebook 02.",
        )
    return InfoModelo(
        variables=paquete["variables"],
        r2_prueba=paquete["r2_prueba"],
        mae_prueba=paquete["mae_prueba"],
        estrategias=modelo.estrategias(),
    )
