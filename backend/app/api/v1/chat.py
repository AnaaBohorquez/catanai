"""Asistente conversacional sobre la recomendación."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.api import PeticionChat, RespuestaChat
from app.services import chat as servicio

router = APIRouter(prefix="/chat", tags=["chat"])


def _ip_cliente(peticion: Request) -> str:
    """
    La IP de quien pregunta. Detrás del proxy de Render llega en X-Forwarded-For
    (la primera de la lista es la del cliente); en local, en la conexión.
    """
    reenviada = peticion.headers.get("x-forwarded-for", "")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return peticion.client.host if peticion.client else "desconocida"


@router.post("", response_model=RespuestaChat, summary="Pregunta sobre la recomendación")
def preguntar(peticion: PeticionChat, solicitud: Request) -> RespuestaChat:
    """
    Responde dudas sobre las opciones que el usuario está viendo.

    El asistente **no inventa recomendaciones ni cifras**: consulta el tablero, las
    opciones y las reglas verificadas con herramientas del backend, y si hace falta
    otra recomendación la pide al modelo. Sin clave de LLM, o si algo falla, responde
    con plantillas construidas sobre las opciones ya calculadas.
    """
    try:
        return servicio.responder(peticion, ip=_ip_cliente(solicitud))
    except servicio.LimiteExcedido as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas preguntas seguidas. Espera unos minutos y vuelve a intentar.",
        ) from error
