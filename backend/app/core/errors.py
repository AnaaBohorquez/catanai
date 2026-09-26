"""Manejo uniforme de errores: el frontend siempre recibe la misma forma."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErrorDeDominio(Exception):
    """Algo que el usuario pidió no tiene sentido en las reglas del juego."""

    def __init__(self, mensaje: str, detalle: str | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle = detalle


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorDeDominio)
    async def _dominio(_: Request, exc: ErrorDeDominio) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": exc.mensaje, "detalle": exc.detalle},
        )

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": "La petición no tiene el formato esperado",
                     "detalle": exc.errors()},
        )
