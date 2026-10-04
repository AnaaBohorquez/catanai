"""Configuración de la aplicación, leída del entorno."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parents[3]
#: La carpeta backend/. El modelo vive aquí y no en la raíz: Vercel solo empaqueta la
#: carpeta del servicio (root "backend"), así que un archivo fuera de ella no llega.
BACKEND = Path(__file__).resolve().parents[2]


class Ajustes(BaseSettings):
    """Ajustes del backend. Cada campo se puede sobrescribir por variable de entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    entorno: str = "desarrollo"
    debug: bool = False

    #: Orígenes autorizados para CORS, separados por coma.
    cors_origins: str = "http://localhost:4200,http://localhost:8080"

    #: Dónde vive el modelo entrenado.
    ruta_modelo: Path = BACKEND / "modelos" / "colono.joblib"

    #: Clave del proveedor de lenguaje para el asistente. Sin ella, el chat
    #: responde con las explicaciones que ya genera el recomendador.
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    #: Esfuerzo de razonamiento: minimal, low, medium o high. Más esfuerzo, más
    #: latencia y más tokens de salida (se cobran aunque no se vean).
    #: "minimal" se eligió con scripts/evaluar_chat.py: p50 3.2 s frente a 4.8 s de
    #: "low", con la misma exactitud (100 % de cifras verificadas).
    openai_esfuerzo: str = "minimal"

    #: Límites del chat con LLM. Evitan que una demo pública agote el saldo.
    chat_max_output_tokens: int = 1200
    chat_max_rondas: int = 4
    chat_preguntas_por_ip: int = 15
    chat_ventana_s: int = 600
    chat_presupuesto_diario_usd: float = 1.0

    @property
    def origenes(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def chat_con_llm(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def obtener_ajustes() -> Ajustes:
    """Los ajustes se leen una sola vez por proceso."""
    return Ajustes()


ajustes = obtener_ajustes()
