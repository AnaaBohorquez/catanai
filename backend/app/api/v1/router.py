"""Ensamblado de la versión 1 de la API."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import chat, meta, recomendaciones, tableros, vision

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(meta.router)
api_router.include_router(tableros.router)
api_router.include_router(recomendaciones.router)
api_router.include_router(vision.router)
api_router.include_router(chat.router)
