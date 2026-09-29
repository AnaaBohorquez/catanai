"""
Límites y registro de consumo del chat con LLM.

La demo es pública: sin límites, cualquiera podría agotar el saldo de la clave. Aquí
viven el límite de preguntas por IP, el presupuesto diario y el registro de cada
pregunta (tokens, latencia y costo), todo en memoria y sin dependencias nuevas.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, date, datetime
from pathlib import Path

from app.core.config import RAIZ, ajustes

#: US$ por millón de tokens: entrada, entrada en caché y salida. Verificado en la
#: página oficial del modelo (developers.openai.com/api/docs/models/gpt-5-mini).
PRECIOS = {"gpt-5-mini": (0.25, 0.025, 2.00)}

RUTA_REGISTRO = RAIZ / "logs" / "consumo.jsonl"


def costo_usd(modelo: str, entrada: int, en_cache: int, salida: int) -> float:
    """
    Costo estimado de una llamada. Los tokens en caché son parte de ``entrada`` y se
    cobran a su tarifa reducida. Un modelo sin precio conocido se estima con el de
    ``gpt-5-mini`` para no dejar el presupuesto sin control.
    """
    p_entrada, p_cache, p_salida = PRECIOS.get(modelo, PRECIOS["gpt-5-mini"])
    normales = max(entrada - en_cache, 0)
    return (normales * p_entrada + en_cache * p_cache + salida * p_salida) / 1_000_000


class LimitadorPorIp:
    """Cuántas preguntas lleva cada IP en la ventana de tiempo."""

    def __init__(self, maximo: int, ventana_s: int) -> None:
        self.maximo = maximo
        self.ventana_s = ventana_s
        self._marcas: dict[str, deque[float]] = defaultdict(deque)
        self._candado = threading.Lock()

    def permitir(self, ip: str, ahora: float | None = None) -> bool:
        ahora = time.monotonic() if ahora is None else ahora
        with self._candado:
            marcas = self._marcas[ip]
            while marcas and ahora - marcas[0] > self.ventana_s:
                marcas.popleft()
            if len(marcas) >= self.maximo:
                return False
            marcas.append(ahora)
            return True


class Presupuesto:
    """Gasto del día en US$. Se reinicia solo al cambiar la fecha."""

    def __init__(self, limite_usd: float) -> None:
        self.limite_usd = limite_usd
        self._dia = date.today()
        self._gastado = 0.0
        self._candado = threading.Lock()

    def _al_dia(self) -> None:
        if date.today() != self._dia:
            self._dia, self._gastado = date.today(), 0.0

    def disponible(self) -> bool:
        with self._candado:
            self._al_dia()
            return self._gastado < self.limite_usd

    def cobrar(self, usd: float) -> None:
        with self._candado:
            self._al_dia()
            self._gastado += usd

    @property
    def gastado(self) -> float:
        return self._gastado


class EstadoClave:
    """
    Si OpenAI rechazó la clave. Mientras esté rechazada no se le pregunta (cada
    intento costaría medio segundo para nada) y /health lo dice; pasado un rato se
    vuelve a probar, por si ya se puso una clave nueva.
    """

    def __init__(self, reintento_s: int = 600) -> None:
        self.reintento_s = reintento_s
        self._rechazada_en: float | None = None
        self._candado = threading.Lock()

    def valida(self, ahora: float | None = None) -> bool:
        ahora = time.monotonic() if ahora is None else ahora
        with self._candado:
            return self._rechazada_en is None or ahora - self._rechazada_en > self.reintento_s

    def rechazada(self, ahora: float | None = None) -> None:
        with self._candado:
            self._rechazada_en = time.monotonic() if ahora is None else ahora

    def aceptada(self) -> None:
        with self._candado:
            self._rechazada_en = None


limitador = LimitadorPorIp(ajustes.chat_preguntas_por_ip, ajustes.chat_ventana_s)
presupuesto = Presupuesto(ajustes.chat_presupuesto_diario_usd)
clave = EstadoClave()


def motivo_sin_llm() -> str | None:
    """Por qué el chat responde en modo básico ahora mismo, o None si usa el LLM."""
    if not ajustes.chat_con_llm:
        return "sin_clave"
    if not clave.valida():
        return "clave_invalida"
    if not presupuesto.disponible():
        return "sin_presupuesto"
    return None


def anonimizar(ip: str) -> str:
    """Un identificador estable durante el día que no revela la IP."""
    return hashlib.sha256(f"{ip}|{date.today()}".encode()).hexdigest()[:12]


def anotar(evento: dict) -> None:
    """
    Una línea JSON por pregunta. Va a la salida estándar (que es lo que muestran los
    logs de Render) y, en desarrollo, también a ``logs/consumo.jsonl``.
    """
    linea = json.dumps(
        {"hora": datetime.now(UTC).isoformat(timespec="seconds"), **evento},
        ensure_ascii=False,
    )
    print(linea, flush=True)
    if ajustes.entorno == "desarrollo":
        try:
            RUTA_REGISTRO.parent.mkdir(exist_ok=True)
            with Path(RUTA_REGISTRO).open("a", encoding="utf-8") as archivo:
                archivo.write(linea + "\n")
        except OSError:
            # Sin disco escribible (por ejemplo, en un contenedor) basta con stdout.
            pass
