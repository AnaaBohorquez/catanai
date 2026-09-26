"""Ajustes comunes a todas las pruebas."""

from __future__ import annotations

import pytest

from app.core.config import ajustes
from app.services import consumo


@pytest.fixture(autouse=True)
def consumo_aislado(monkeypatch) -> list[dict]:
    """
    Cada prueba empieza sin clave de OpenAI, con límites y presupuesto limpios, y
    los eventos de consumo se guardan en una lista en vez de escribirse en ``logs/``.

    Sin clave: aunque ``backend/.env`` tenga una real, las pruebas nunca llaman a la
    red ni gastan saldo. Las que prueban el LLM usan un cliente simulado.
    """
    monkeypatch.setattr(ajustes, "openai_api_key", "")
    eventos: list[dict] = []
    monkeypatch.setattr(consumo, "limitador", consumo.LimitadorPorIp(1000, 600))
    monkeypatch.setattr(consumo, "presupuesto", consumo.Presupuesto(1.0))
    monkeypatch.setattr(consumo, "anotar", eventos.append)
    return eventos
