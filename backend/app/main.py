"""Punto de entrada de la API de Colono IA."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import ajustes
from app.core.errors import registrar_manejadores

DESCRIPCION = """\
Recomendador de colocación inicial en Catan.

A partir del tablero recién armado, calcula qué pareja de poblados conviene y
explica por qué. El modelo es una regresión lineal entrenada sobre partidas
simuladas, y las familias de estrategia salen de un agrupamiento.
"""

app = FastAPI(
    title="Colono IA",
    version="0.1.0",
    description=DESCRIPCION,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ajustes.origenes,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

registrar_manejadores(app)
app.include_router(api_router)


@app.middleware("http")
async def medir_tiempo(
    peticion: Request, siguiente: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Añade a cada respuesta cuánto tardó, útil para la demo y para depurar."""
    inicio = time.perf_counter()
    respuesta = await siguiente(peticion)
    respuesta.headers["X-Tiempo-ms"] = f"{(time.perf_counter() - inicio) * 1000:.0f}"
    return respuesta


@app.get("/", include_in_schema=False)
def raiz() -> dict:
    return {"servicio": "Colono IA", "docs": "/docs", "api": "/api/v1"}
