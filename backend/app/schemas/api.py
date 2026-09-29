"""
Contratos de la API.

Estos esquemas son la única fuente de verdad del formato que hablan backend y
frontend. FastAPI genera el OpenAPI a partir de ellos, y de ahí se derivan los
tipos de TypeScript, para que el frontend nunca los redefina a mano.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Terreno = Literal["bosque", "pastos", "campos", "colinas", "montanas", "desierto"]
Recurso = Literal["madera", "ladrillo", "trigo", "oveja", "mineral"]
Momento = Literal["primera", "segunda"]


# --- Tablero ---------------------------------------------------------------

class Hexagono(BaseModel):
    id: str = Field(description="Coordenada axial, por ejemplo '0,-2'")
    q: int
    r: int
    terreno: Terreno
    recurso: Recurso | None = None
    numero: int | None = Field(default=None, ge=2, le=12)
    pips: int = 0


class Puerto(BaseModel):
    vertices: list[str] = Field(min_length=2, max_length=2)
    tipo: str = Field(description="'3:1' o el nombre de un recurso para el 2:1")


class Vertice(BaseModel):
    id: str
    hexagonos: list[str]
    puerto: str | None = None


class Arista(BaseModel):
    vertices: list[str] = Field(min_length=2, max_length=2)


class Tablero(BaseModel):
    hexagonos: list[Hexagono]
    puertos: list[Puerto] = []
    vertices: list[Vertice] = []
    aristas: list[Arista] = []
    semilla: int | None = None


class TableroConAvisos(BaseModel):
    tablero: Tablero
    avisos: list[str] = Field(
        default=[],
        description="Incumplimientos de las reglas del juego base. No bloquean el cálculo.",
    )


# --- Recomendación ---------------------------------------------------------

class PeticionRecomendar(BaseModel):
    tablero: Tablero
    jugadores: int = Field(default=4, ge=3, le=4)
    ocupados: list[str] = Field(
        default=[], description="Vértices que ya tomaron otros jugadores"
    )
    mio: str | None = Field(
        default=None,
        description=(
            "Tu primer poblado, si ya lo colocaste. Con esto la búsqueda deja de "
            "ser de parejas y pasa a buscar el mejor compañero."
        ),
    )
    cuantas: int = Field(default=3, ge=1, le=6)


class Explicacion(BaseModel):
    titulo: str
    resumen: str
    produccion: str
    porque: list[str]
    haz: str
    evita: str


class Opcion(BaseModel):
    vertices: list[str] = Field(min_length=2, max_length=2)
    descripciones: list[str] = Field(min_length=2, max_length=2)
    prediccion: float = Field(description="Puntos de victoria estimados en 20 rondas")
    estrategia: str
    explicacion: Explicacion
    variables: dict[str, float]


class RespuestaRecomendar(BaseModel):
    momento: Momento
    opciones: list[Opcion]
    parejas_evaluadas: int
    avisos: list[str] = []


# --- Visión ----------------------------------------------------------------

class HexagonoDetectado(BaseModel):
    id: str
    terreno: Terreno
    numero: int | None = None
    confianza_terreno: float = Field(ge=0, le=1)
    confianza_numero: float = Field(ge=0, le=1)


class RespuestaVision(BaseModel):
    tablero: Tablero
    detecciones: list[HexagonoDetectado]
    puertos_confirmados: bool = Field(
        default=False,
        description="La foto no lee puertos: llegan como plantilla que el usuario confirma",
    )
    avisos: list[str] = []
    mensaje: str = Field(
        description="Qué debe revisar el usuario antes de calcular"
    )


# --- Chat ------------------------------------------------------------------

class Mensaje(BaseModel):
    rol: Literal["usuario", "asistente"]
    texto: str


class PeticionChat(BaseModel):
    pregunta: str = Field(min_length=1, max_length=500)
    historial: list[Mensaje] = []
    tablero: Tablero | None = None
    opciones: list[Opcion] = Field(
        default=[], description="Las recomendaciones que el usuario está viendo"
    )
    elegida: int = Field(
        default=0, ge=0, le=5,
        description="Índice (desde 0) de la opción que el usuario eligió en pantalla",
    )
    # Estado de la colocación tal como lo marcó el usuario en el tablero: el chat
    # lo recibe siempre para no recomendar sobre un tablero que ya no es el real.
    ocupados: list[str] = Field(default=[], description="Vértices marcados como de rivales")
    mio: str | None = Field(default=None, description="Primer poblado del usuario, si lo marcó")
    jugadores: int = Field(default=4, ge=3, le=4)


class EstadoColocacion(BaseModel):
    """Marcas del tablero: lo que el frontend debe mostrar como ocupado y como propio."""

    ocupados: list[str] = []
    mio: str | None = None


class RespuestaChat(BaseModel):
    texto: str
    fuente: Literal["modelo_de_lenguaje", "plantillas"] = Field(
        description="Si respondió el LLM o el motor de reglas del recomendador"
    )
    fuentes: list[Literal["modelo", "reglas", "general"]] = Field(
        default=[],
        description=(
            "De dónde sale el contenido: resultados del modelo, reglas verificadas o "
            "consejo general no calculado. La interfaz lo muestra como etiquetas."
        ),
    )
    estado_nuevo: EstadoColocacion | None = Field(
        default=None,
        description=(
            "Si el asistente recalculó con una hipótesis ('¿y si un rival toma…?'), las "
            "marcas que la interfaz debe aplicar para que tablero y opciones coincidan"
        ),
    )
    opciones_nuevas: list[Opcion] | None = Field(
        default=None,
        description="Si el asistente pidió otra recomendación, las que calculó el modelo",
    )


# --- Meta ------------------------------------------------------------------

class Salud(BaseModel):
    estado: Literal["ok", "degradado"]
    version: str
    modelo_cargado: bool
    chat_con_llm: bool
    chat_motivo: Literal["sin_clave", "clave_invalida", "sin_presupuesto"] | None = Field(
        default=None,
        description="Por qué el chat responde en modo básico (sin LLM), si es el caso",
    )


class InfoModelo(BaseModel):
    variables: list[str]
    r2_prueba: float
    mae_prueba: float
    estrategias: list[str]
