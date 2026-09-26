"""
Cálculo completo de una recomendación, del tablero de la API a la respuesta.

Vive aquí y no en el endpoint para que el endpoint ``/recomendar`` y la herramienta
del chat que pide recomendaciones nuevas usen exactamente el mismo cálculo.
"""

from __future__ import annotations

from app.core.errors import ErrorDeDominio
from app.domain.simulador import parejas_candidatas
from app.schemas.api import (
    Explicacion,
    Opcion,
    PeticionRecomendar,
    RespuestaRecomendar,
)
from app.services import modelo
from app.services.recomendador import describir_vertice, recomendar
from app.services.serializers import (
    avisos_del_tablero,
    id_vertice,
    tablero_desde_api,
    vertice_desde_id,
)


class ModeloNoDisponible(Exception):
    """El modelo no se pudo cargar: la API responde 503 en vez de fallar al arrancar."""


def calcular(peticion: PeticionRecomendar) -> RespuestaRecomendar:
    """
    Las mejores opciones de colocación para el tablero de la petición.

    Raises
    ------
    ModeloNoDisponible
        Si el modelo no está cargado.
    ErrorDeDominio
        Si los vértices no existen, se contradicen o bloquean todo el tablero.
    """
    paquete = modelo.paquete()
    if paquete is None:
        raise ModeloNoDisponible

    tablero = tablero_desde_api(peticion.tablero.model_dump())

    try:
        ocupados = {vertice_desde_id(v) for v in peticion.ocupados}
        mio = vertice_desde_id(peticion.mio) if peticion.mio else None
    except KeyError as error:
        raise ErrorDeDominio("Identificador de vértice desconocido", str(error)) from error

    if mio is not None and mio in ocupados:
        raise ErrorDeDominio(
            "Tu primer poblado no puede estar marcado como ocupado por otro jugador"
        )

    candidatas = parejas_candidatas(tablero, ocupados=ocupados, obligatorio=mio)
    if not candidatas:
        raise ErrorDeDominio(
            "No quedan colocaciones legales",
            "Revisa los vértices marcados como ocupados: puede que bloqueen todo el tablero.",
        )

    resultados = recomendar(
        tablero, paquete,
        ocupados=ocupados, jugadores=peticion.jugadores,
        cuantas=peticion.cuantas, mio=mio,
    )

    return RespuestaRecomendar(
        momento="segunda" if mio else "primera",
        parejas_evaluadas=len(candidatas),
        avisos=avisos_del_tablero(tablero),
        opciones=[
            Opcion(
                vertices=[id_vertice(v) for v in r["vertices"]],
                descripciones=[describir_vertice(v, tablero) for v in r["vertices"]],
                prediccion=round(r["prediccion"], 2),
                estrategia=r["estrategia"],
                explicacion=Explicacion(**r["explicacion"]),
                variables={k: round(float(v), 4) for k, v in r["variables"].items()},
            )
            for r in resultados
        ],
    )
