"""
Herramientas que el asistente puede usar: la única vía por la que conoce datos.

El modelo de lenguaje no ve el tablero ni las opciones directamente: las pide con
estas funciones, que leen lo que ya calculó el recomendador o las reglas
verificadas. Así cada cifra de una respuesta se puede rastrear hasta una salida de
herramienta, que es lo que revisa el verificador de ``services/chat.py``.

Todas son de solo lectura, salvo en un sentido: ``solicitar_recomendacion`` calcula
opciones nuevas, y el chat se las devuelve al frontend para que las dibuje.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from app.core.errors import ErrorDeDominio
from app.domain import partida
from app.domain.reglas import buscar_reglas, reglas_verificadas
from app.domain.simulador import TOPOLOGIA
from app.domain.tablero import COSTOS, PIPS, RECURSOS
from app.domain.variables import _tasa_de_cambio, pips_por_recurso_del_tablero
from app.schemas.api import (
    Destino,
    EstadoColocacion,
    Opcion,
    PeticionChat,
    PeticionExpansion,
    PeticionRecomendar,
)
from app.services import expansion, modelo
from app.services.recomendacion import ModeloNoDisponible, calcular
from app.services.recomendador import ESTRATEGIAS, describir_vertice, perfil_de_familia
from app.services.serializers import id_vertice, tablero_desde_api, vertice_desde_id

#: Puntos de victoria que da cada pieza al construirla. La carta de desarrollo no
#: da puntos por sí misma (salvo que sea de punto de victoria).
PUNTOS_POR_PIEZA = {"camino": 0, "poblado": 1, "ciudad": 2, "carta_desarrollo": 0}

NOTAS_POR_PIEZA = {
    "camino": "Se coloca en una arista pegada a tus caminos, poblados o ciudades.",
    "poblado": "Debe conectarse a un camino tuyo y respetar la regla de distancia.",
    "ciudad": "Sustituye a un poblado tuyo: pasas de 1 a 2 puntos y produces el doble.",
    "carta_desarrollo": (
        "Se compra al banco; puede ser caballero, punto de victoria o progreso."
    ),
}

#: Límite de caracteres de cada salida: acota los tokens de entrada por ronda.
LIMITE_SALIDA = 4000

Fuente = Literal["modelo", "reglas"]

#: Cómo se nombra un vértice en el chat: tal como se ve en pantalla. El modelo de
#: lenguaje nunca ve ni escribe ids internos, así que no puede inventarlos.
_REFERENCIA = {
    "type": "object",
    "properties": {
        "opcion": {"type": "integer", "description": "Número de la opción en pantalla"},
        "poblado": {"type": "integer", "description": "1 o 2: cuál de sus dos poblados"},
    },
    "required": ["opcion", "poblado"],
    "additionalProperties": False,
}

#: Definiciones en el formato de la Responses API. `strict` obliga al modelo a
#: respetar el esquema; por eso todo campo aparece en `required` (los opcionales
#: admiten null).
DEFINICIONES = [
    {
        "type": "function",
        "name": "consultar_reglas",
        "description": (
            "Busca en las reglas oficiales verificadas de Catan (juego base). Úsala para "
            "cualquier pregunta sobre reglas: costos, el 7 y el ladrón, comercio y "
            "puertos, puntos de victoria, colocación inicial, etc."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "tema": {"type": "string", "description": "Tema o pregunta, en español"},
            },
            "required": ["tema"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "ver_resultados_actuales",
        "description": (
            "Devuelve las opciones de colocación que el usuario tiene en pantalla, "
            "calculadas por el modelo: familia de estrategia, puntos estimados, "
            "producción por recurso, puertos, explicación y cuál está seleccionada."
        ),
        "strict": True,
        "parameters": {
            "type": "object", "properties": {}, "required": [], "additionalProperties": False
        },
    },
    {
        "type": "function",
        "name": "comparar_opciones",
        "description": "Diferencias entre dos opciones en pantalla (números desde 1).",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "Número de la primera opción"},
                "b": {"type": "integer", "description": "Número de la segunda opción"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "solicitar_recomendacion",
        "description": (
            "Pide al modelo una recomendación nueva sobre el tablero actual (con las "
            "marcas del usuario), sumando cambios: vértices que tomaría un rival o el "
            "primer poblado del usuario. Los vértices se nombran como en pantalla: "
            "opción N, poblado K (K es 1 o 2)."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "ocupar": {
                    "type": "array",
                    "items": _REFERENCIA,
                    "description": "Poblados de las opciones en pantalla que toma un rival",
                },
                "mio": {
                    "anyOf": [_REFERENCIA, {"type": "null"}],
                    "description": "Dónde puso el usuario su primer poblado; null si no cambia",
                },
                "jugadores": {
                    "type": ["integer", "null"],
                    "description": "3 o 4; null para conservar el número actual",
                },
            },
            "required": ["ocupar", "mio", "jugadores"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "ver_estado_del_tablero",
        "description": (
            "Lo que el usuario marcó en el tablero: su primer poblado, los poblados de "
            "rivales, si es la primera o la segunda colocación y cuántos vértices libres "
            "quedan por la regla de distancia."
        ),
        "strict": True,
        "parameters": {
            "type": "object", "properties": {}, "required": [], "additionalProperties": False
        },
    },
]

_PIEZAS = ["camino", "poblado", "ciudad", "carta_desarrollo"]

#: Herramientas de "experto en Catan": costos, mano, cómo conseguir un recurso,
#: ritmo de construcción, probabilidades y el tablero. Todas calculan a partir del
#: dominio (COSTOS, PIPS, tasas de cambio, variables de la opción), no de memoria.
DEFINICIONES_EXPERTO = [
    {
        "type": "function",
        "name": "costo_de_construccion",
        "description": (
            "Costo en recursos y puntos de victoria de camino, poblado, ciudad o carta de "
            "desarrollo (o de todas). Úsala para '¿cuánto cuesta…?' o '¿qué necesito para…?'."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"pieza": {"type": "string", "enum": [*_PIEZAS, "todas"]}},
            "required": ["pieza"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "que_me_falta",
        "description": (
            "Dada la mano del usuario, dice si alcanza para una pieza, qué recursos le "
            "faltan y si puede completarlos cambiando su sobrante con el banco o sus "
            "puertos. Úsala siempre que el usuario diga qué cartas tiene."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "mano": {
                    "type": "object",
                    "properties": {r: {"type": "integer"} for r in RECURSOS},
                    "required": list(RECURSOS),
                    "additionalProperties": False,
                    "description": "Cartas de cada recurso (0 si no tiene)",
                },
                "pieza": {"type": "string", "enum": _PIEZAS},
            },
            "required": ["mano", "pieza"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "como_conseguir",
        "description": (
            "Cómo obtener un recurso con la opción seleccionada: cuánto lo produce, "
            "cuántas cartas espera por ronda y cuál es el mejor cambio (banco o puerto) "
            "para conseguirlo a partir de lo que sí produce."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"recurso": {"type": "string", "enum": list(RECURSOS)}},
            "required": ["recurso"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "plan_de_construccion",
        "description": (
            "Para la opción seleccionada: rondas estimadas hasta poder construir camino, "
            "poblado, ciudad y carta de desarrollo (contando el comercio con el banco) y "
            "cartas esperadas por ronda de cada recurso."
        ),
        "strict": True,
        "parameters": {
            "type": "object", "properties": {}, "required": [], "additionalProperties": False
        },
    },
    {
        "type": "function",
        "name": "probabilidad_de_numero",
        "description": "Probabilidad de que salga un número (2 a 12) al tirar dos dados.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"numero": {"type": "integer", "description": "De 2 a 12"}},
            "required": ["numero"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "resumen_del_tablero",
        "description": (
            "Resumen del tablero actual: producción total de cada recurso (qué escasea), "
            "los números de cada recurso y los puertos que hay."
        ),
        "strict": True,
        "parameters": {
            "type": "object", "properties": {}, "required": [], "additionalProperties": False
        },
    },
    {
        "type": "function",
        "name": "explicar_estrategia",
        "description": (
            "La estrategia de juego de una opción: cómo se gana con su familia, por qué el "
            "modelo la puso en esa familia, un plan ordenado de qué construir primero y en "
            "cuántas rondas, y qué opción en pantalla representa a cada otra familia. "
            "Úsala para '¿qué estrategia…?', '¿cómo juego…?', '¿qué hago después?', "
            "'¿cómo gano?' o '¿y si juego Ciudades?'."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "familia": {
                    "type": ["string", "null"],
                    "enum": [*ESTRATEGIAS, None],
                    "description": "null = la familia de la opción seleccionada",
                },
            },
            "required": ["familia"],
            "additionalProperties": False,
        },
    },
]

DEFINICIONES = DEFINICIONES + DEFINICIONES_EXPERTO + [
    {
        "type": "function",
        "name": "mi_produccion",
        "description": (
            "En partida (ya colocaste tus poblados): lo que producen TODAS tus piezas "
            "(las ciudades cuentan doble): pips y cartas por ronda de cada recurso, qué "
            "números te pagan, qué no produces, tus puertos, rondas estimadas hasta cada "
            "construcción y cuántas piezas te quedan. Úsala para '¿qué construyo "
            "ahora?', '¿qué hago?', '¿qué produzco?', '¿qué me conviene?'."
        ),
        "strict": True,
        "parameters": {
            "type": "object", "properties": {}, "required": [], "additionalProperties": False
        },
    },
    {
        "type": "function",
        "name": "hacia_donde_expandir",
        "description": (
            "Con la colocación inicial completa (o con tu primer poblado puesto): los "
            "mejores vértices para tu siguiente poblado (A, B y C), cuántos caminos "
            "hacen falta, qué recursos nuevos dan, puerto y si un rival está cerca. "
            "Úsala para '¿hacia dónde crezco?', '¿hacia dónde tiendo mis caminos?', "
            "'¿dónde va mi tercer poblado?', '¿cómo sigo mi estrategia?'."
        ),
        "strict": True,
        "parameters": {
            "type": "object", "properties": {}, "required": [], "additionalProperties": False
        },
    },
]

#: Qué mide cada capacidad del agrupamiento, en palabras de jugador.
SIGNIFICADO_CAPACIDAD = {
    "par_camino": "pips de madera y ladrillo a la vez (el menor de los dos)",
    "par_ciudad": "trigo y mineral en la proporción de la ciudad (2 y 3)",
    "trio_desarrollo": "pips de trigo, oveja y mineral a la vez (el menor de los tres)",
    "cuarteto_poblado": "los cuatro recursos del poblado a la vez",
    "puerto_alineado": "1 si tiene puerto 2:1 del recurso que más produce",
    "desequilibrio": "fracción de la producción que viene de un solo recurso",
}

#: Cómo se llega a 10 puntos con cada familia.
COMO_SE_GANA = {
    "expansion": "Muchos poblados (1 punto cada uno) y la carta de camino más largo "
                 "(2 puntos).",
    "ciudades": "Ciudades (2 puntos cada una) y cartas de desarrollo: ejército mayor "
                "(2 puntos) y cartas de punto de victoria.",
    "puerto": "Conviertes tu recurso dominante 2:1 en lo que te falte y construyes de todo "
              "sin depender de los demás.",
    "desequilibrada": "Es difícil: necesitas un puerto o comerciar mucho para gastar lo que "
                      "produces.",
}

#: Orden de construcción que prioriza cada familia. "acumular" es juntar el recurso
#: dominante para cambiarlo en el puerto; "puerto" es llegar a uno.
PRIORIDAD = {
    "expansion": ["camino", "poblado", "ciudad"],
    "ciudades": ["ciudad", "carta_desarrollo", "poblado"],
    "puerto": ["acumular", "poblado", "ciudad"],
    "desequilibrada": ["puerto", "camino", "poblado"],
}


@dataclass
class Herramientas:
    """Ejecuta las herramientas sobre lo que el usuario tiene en pantalla."""

    peticion: PeticionChat
    #: Qué herramientas se usaron y de qué fuente vino cada dato.
    usadas: list[str] = field(default_factory=list)
    fuentes: set[Fuente] = field(default_factory=set)
    #: Todas las salidas, para que el verificador compruebe las cifras.
    salidas: list[str] = field(default_factory=list)
    opciones_nuevas: list[Opcion] | None = None
    #: Destinos para el siguiente poblado, si se calcularon: el tablero los dibuja.
    destinos: list[Destino] | None = None
    #: Las marcas con las que se calcularon las opciones nuevas.
    estado_nuevo: EstadoColocacion | None = None

    def ejecutar(self, nombre: str, argumentos: str) -> str:
        """Corre una herramienta y devuelve su salida en JSON (o un error legible)."""
        self.usadas.append(nombre)
        try:
            datos = json.loads(argumentos or "{}")
            funcion = getattr(self, f"_{nombre}", None)
            if funcion is None:
                salida = {"error": f"Herramienta desconocida: {nombre}"}
            else:
                salida = funcion(**datos)
        except (TypeError, ValueError) as error:
            salida = {"error": f"Argumentos inválidos: {error}"}
        texto = json.dumps(salida, ensure_ascii=False)[:LIMITE_SALIDA]
        self.salidas.append(texto)
        return texto

    # --- Herramientas ------------------------------------------------------

    def _consultar_reglas(self, tema: str) -> dict:
        encontradas = buscar_reglas(tema, reglas_verificadas())
        if not encontradas:
            return {"reglas": [], "nota": "No hay una regla verificada sobre ese tema."}
        self.fuentes.add("reglas")
        return {
            "reglas": [
                {"id": r["id"], "texto": r["texto"], "fuente": r["fuente"]} for r in encontradas
            ]
        }

    def _ver_resultados_actuales(self) -> dict:
        opciones = self.peticion.opciones
        if not opciones:
            return {"opciones": [], **self._sin_opciones()}
        self.fuentes.add("modelo")
        return {
            "nota": "puntos_estimados son una estimación del simulador; importa más el orden.",
            "seleccionada": self._seleccionada() + 1,
            "opciones": [self._resumir(i, o) for i, o in enumerate(opciones)],
        }

    def _comparar_opciones(self, a: int, b: int) -> dict:
        opciones = self.peticion.opciones
        if not (1 <= a <= len(opciones) and 1 <= b <= len(opciones)):
            return {"error": f"Solo hay {len(opciones)} opciones en pantalla."}
        self.fuentes.add("modelo")
        oa, ob = opciones[a - 1], opciones[b - 1]
        return {
            "a": self._resumir(a - 1, oa),
            "b": self._resumir(b - 1, ob),
            "diferencia_puntos_estimados": round(oa.prediccion - ob.prediccion, 2),
            "diferencia_pips_por_recurso": {
                r: round(oa.variables.get(f"pips_{r}", 0) - ob.variables.get(f"pips_{r}", 0), 2)
                for r in RECURSOS
            },
        }

    def _solicitar_recomendacion(
        self, ocupar: list[dict], mio: dict | None = None, jugadores: int | None = None
    ) -> dict:
        if self.peticion.tablero is None:
            return {"error": "No hay tablero cargado."}

        # Siempre se parte de lo marcado en el tablero y se le suman los cambios.
        ocupados = list(self.peticion.ocupados)
        propio = self.peticion.mio
        for referencia in ocupar:
            vertice = self._resolver(referencia)
            if isinstance(vertice, dict):
                return vertice
            if vertice == propio:
                return {"error": "Ese es el poblado del usuario; no puede tomarlo un rival."}
            if vertice not in ocupados:
                if self._bloqueado(vertice, ocupados, propio):
                    return {"error": "Un rival no puede colocar ahí: está junto a otro poblado "
                                     "(regla de distancia)."}
                ocupados.append(vertice)
        if mio is not None:
            vertice = self._resolver(mio)
            if isinstance(vertice, dict):
                return vertice
            if vertice in ocupados or self._bloqueado(vertice, ocupados, None):
                return {"error": "Ese vértice está ocupado o junto a un poblado rival "
                                 "(regla de distancia)."}
            propio = vertice

        try:
            respuesta = calcular(
                PeticionRecomendar(
                    tablero=self.peticion.tablero,
                    jugadores=jugadores or self.peticion.jugadores,
                    ocupados=ocupados,
                    mio=propio,
                )
            )
        except ModeloNoDisponible:
            return {"error": "El modelo no está disponible en el servidor."}
        except ErrorDeDominio as error:
            return {"error": error.mensaje}
        except ValueError as error:
            return {"error": f"Petición inválida: {error}"}
        self.fuentes.add("modelo")
        self.opciones_nuevas = respuesta.opciones
        self.estado_nuevo = EstadoColocacion(ocupados=ocupados, mio=propio)
        return {
            "nota": (
                "Estas opciones ya se muestran en pantalla y reemplazan a las anteriores; "
                "el tablero marca los cambios."
            ),
            "momento": "segunda colocación" if propio else "primera colocación",
            "opciones": [self._resumir(i, o) for i, o in enumerate(respuesta.opciones)],
        }

    def _ver_estado_del_tablero(self) -> dict:
        if self.peticion.tablero is None:
            return {"error": "No hay tablero cargado."}
        self.fuentes.add("modelo")
        ocupados, propio = self.peticion.ocupados, self.peticion.mio
        propios = self._propios()
        libres = [
            v for v in TOPOLOGIA.vertices
            if not any(
                self._bloqueado(id_vertice(v), ocupados, p)
                for p in [*propios, *self.peticion.ciudades] or [None]
            )
        ]
        ciudades = list(self.peticion.ciudades)
        if self._en_partida():
            momento = "partida en curso: la colocación inicial ya terminó"
        else:
            momento = "segunda colocación" if propio else "primera colocación"
        return {
            "momento": momento,
            "tus_poblados": [self._describir(p) for p in propios] or "aún no colocas",
            "tus_ciudades": [self._describir(c) for c in ciudades],
            "rivales_marcados": len(ocupados),
            "poblados_rivales": [self._describir(v) for v in ocupados],
            "vertices_libres_legales": len(libres),
            "jugadores": self.peticion.jugadores,
        }

    # --- Experto en Catan ---------------------------------------------------

    def _costo_de_construccion(self, pieza: str) -> dict:
        piezas = _PIEZAS if pieza == "todas" else [pieza]
        if any(p not in COSTOS for p in piezas):
            return {"error": f"Pieza desconocida: {pieza}"}
        self.fuentes.add("reglas")
        return {
            p: {
                "costo": COSTOS[p],
                "puntos_de_victoria": PUNTOS_POR_PIEZA[p],
                "nota": NOTAS_POR_PIEZA[p],
            }
            for p in piezas
        }

    def _que_me_falta(self, mano: dict, pieza: str) -> dict:
        if pieza not in COSTOS:
            return {"error": f"Pieza desconocida: {pieza}"}
        mano = {r: int(mano.get(r, 0)) for r in RECURSOS}
        if any(n < 0 for n in mano.values()):
            return {"error": "La mano no puede tener cartas negativas."}
        self.fuentes.add("reglas")
        costo = COSTOS[pieza]
        faltan = {r: c - mano[r] for r, c in costo.items() if mano[r] < c}

        # Lo que sobra después de pagar la pieza se puede cambiar, cada recurso a
        # su propia tasa (2:1 si hay puerto de ese recurso, 3:1 genérico, 4:1 banco).
        puertos = self._puertos_seleccionada()
        sobrante = {r: mano[r] - costo.get(r, 0) for r in RECURSOS if mano[r] > costo.get(r, 0)}
        cambios = self._planear_cambios(sobrante, sum(faltan.values()), puertos)
        return {
            "pieza": pieza,
            "costo": costo,
            "alcanza_ya": not faltan,
            "faltan": faltan,
            "puede_completar_cambiando": len(cambios) >= sum(faltan.values()),
            "cambios_sugeridos": cambios,
            "puertos_considerados": sorted(puertos) or ["ninguno: solo banco 4:1"],
            "nota": (
                "En Catan los recursos no se compran: se producen o se cambian con el banco, "
                "un puerto u otros jugadores en tu turno."
            ),
        }

    def _como_conseguir(self, recurso: str) -> dict:
        if recurso not in RECURSOS:
            return {"error": f"Recurso desconocido: {recurso}"}
        opcion = self._opcion_seleccionada()
        en_partida = None
        if opcion is None and self._en_partida():
            en_partida = self._resumen_de_partida()
        if opcion is None and en_partida is None:
            return self._sin_opciones()
        self.fuentes.add("modelo")
        puertos = self._puertos_seleccionada()
        ritmo = en_partida["cartas_por_ronda"] if en_partida else self._cartas_por_ronda(opcion)
        pips_propios = (
            en_partida["pips_por_recurso"][recurso] if en_partida
            else opcion.variables.get(f"pips_{recurso}", 0)
        )
        # Para conseguir `recurso` se entrega otro; conviene el que más se produce
        # por cada carta que cuesta cambiarlo.
        fuentes_de_cambio = sorted(
            (
                {
                    "entregar": r,
                    "tasa": f"{_tasa_de_cambio(r, puertos)}:1",
                    "cartas_entregadas_por_ronda": ritmo[r],
                    "cartas_conseguidas_por_ronda": round(
                        ritmo[r] / _tasa_de_cambio(r, puertos), 3
                    ),
                }
                for r in RECURSOS
                if r != recurso and ritmo[r] > 0
            ),
            key=lambda c: -c["cartas_conseguidas_por_ronda"],
        )
        propio = ritmo[recurso]
        return {
            "recurso": recurso,
            "pips_propios": pips_propios,
            "cartas_por_ronda_produciendo": propio,
            "rondas_por_carta": round(1 / propio, 1) if propio > 0 else None,
            "mejores_cambios": fuentes_de_cambio[:2],
            "tus_puertos": sorted(puertos) or ["ninguno"],
            "nota": (
                "Ronda = cada jugador tira una vez. También puedes comerciar con otros "
                "jugadores."
            ),
        }

    def _plan_de_construccion(self) -> dict:
        opcion = self._opcion_seleccionada()
        if opcion is None and self._en_partida() and (datos := self._resumen_de_partida()):
            self.fuentes.add("modelo")
            return {
                "tus_piezas": datos["piezas"],
                "rondas_estimadas_hasta": datos["rondas_hasta"],
                "cartas_por_ronda": datos["cartas_por_ronda"],
                "nota": "Con la producción de todas tus piezas (las ciudades cuentan doble).",
            }
        if opcion is None:
            return self._sin_opciones()
        self.fuentes.add("modelo")
        v = opcion.variables
        return {
            "opcion": self._seleccionada() + 1,
            "rondas_estimadas_hasta": {
                p: round(v.get(f"turnos_a_{p}", 0), 1) for p in _PIEZAS
            },
            "cartas_por_ronda": self._cartas_por_ronda(opcion),
            "nota": (
                "Estimación con la producción esperada de tus dos poblados y el cambio 4:1, "
                "3:1 o 2:1 para lo que no produces. Ronda = cada jugador tira una vez."
            ),
        }

    def _probabilidad_de_numero(self, numero: int) -> dict:
        if numero not in PIPS:
            return {"error": "Con dos dados solo salen números del 2 al 12."}
        self.fuentes.add("reglas")
        pips = PIPS[numero]
        salida = {
            "numero": numero,
            "combinaciones_de_36": pips,
            "probabilidad": round(pips / 36, 4),
            "porcentaje": round(100 * pips / 36, 1),
        }
        if numero == 7:
            salida["nota"] = "El 7 no produce recursos: activa el ladrón y el descarte."
        else:
            salida["nota"] = f"Los puntitos de la ficha del {numero} son {pips}: sus pips."
        return salida

    def _resumen_del_tablero(self) -> dict:
        if self.peticion.tablero is None:
            return {"error": "No hay tablero cargado."}
        self.fuentes.add("modelo")
        dominio = tablero_desde_api(self.peticion.tablero.model_dump())
        pips = pips_por_recurso_del_tablero(dominio)
        numeros: dict[str, list[int]] = {r: [] for r in RECURSOS}
        for h in self.peticion.tablero.hexagonos:
            if h.recurso and h.numero:
                numeros[h.recurso].append(h.numero)
        puertos: dict[str, int] = {}
        for p in self.peticion.tablero.puertos:
            puertos[p.tipo] = puertos.get(p.tipo, 0) + 1
        # Los empates se devuelven juntos: ordenar sin más haría que el asistente
        # afirmara que uno escasea más que otro con los mismos pips.
        minimo, maximo = min(pips.values()), max(pips.values())
        return {
            "pips_totales_por_recurso": pips,
            "mas_escasos": [r for r in RECURSOS if pips[r] == minimo],
            "mas_abundantes": [r for r in RECURSOS if pips[r] == maximo],
            "del_mas_escaso_al_mas_abundante": sorted(RECURSOS, key=lambda r: pips[r]),
            "numeros_por_recurso": {
                r: sorted(ns, key=lambda n: -PIPS[n]) for r, ns in numeros.items()
            },
            "puertos": puertos or {"ninguno": 0},
        }

    def _explicar_estrategia(self, familia: str | None = None) -> dict:
        opciones = self.peticion.opciones
        if familia is not None and familia not in ESTRATEGIAS:
            return {"error": f"Familia desconocida: {familia}. Son: {', '.join(ESTRATEGIAS)}."}
        if familia is None:
            if not opciones:
                return self._sin_opciones()
            familia = self._opcion_seleccionada().estrategia

        # La opción que representa a la familia: la seleccionada si es de ella; si no,
        # la mejor en pantalla de esa familia (las opciones vienen ordenadas).
        seleccionada = self._opcion_seleccionada()
        if seleccionada is not None and seleccionada.estrategia == familia:
            indice = self._seleccionada()
        else:
            indice = next((i for i, o in enumerate(opciones) if o.estrategia == familia), None)

        self.fuentes.add("modelo")
        ficha = ESTRATEGIAS[familia]
        salida: dict = {
            "familia": ficha["nombre"],
            "resumen": ficha["resumen"],
            "como_se_gana": COMO_SE_GANA[familia],
            "haz": ficha["haz"],
            "evita": ficha["evita"],
        }
        if indice is None:
            salida["nota"] = "Ninguna opción en pantalla es de esta familia."
        else:
            opcion = opciones[indice]
            salida["opcion"] = indice + 1
            salida["puntos_estimados"] = opcion.prediccion
            salida["por_que_es_de_esta_familia"] = self._comparar_con_familia(opcion, familia)
            salida["plan"] = self._plan_de_familia(opcion, familia)
        salida["otras_familias_en_pantalla"] = [
            {
                "opcion": i + 1,
                "familia": o.explicacion.titulo,
                "puntos_estimados": o.prediccion,
            }
            for i, o in enumerate(opciones)
            if o.estrategia != familia
        ]
        return salida

    def _hacia_donde_expandir(self) -> dict:
        if self.peticion.tablero is None:
            return {"error": "No hay tablero cargado."}
        propios, ciudades = self._propios(), list(self.peticion.ciudades)
        if not propios and not ciudades:
            return {"error": "Primero marca tus poblados en el tablero (Mi poblado)."}
        try:
            respuesta = expansion.calcular(
                PeticionExpansion(
                    tablero=self.peticion.tablero,
                    propios=propios,
                    ciudades=ciudades,
                    ocupados=self.peticion.ocupados,
                )
            )
        except ErrorDeDominio as error:
            return {"error": error.mensaje}
        self.fuentes.add("modelo")
        self.destinos = respuesta.destinos
        if not respuesta.destinos:
            return {"destinos": [], "nota": "No hay vértices libres a 2 o 3 caminos."}
        return {
            "nota": (
                "Puntaje = pips + 0.5 × pips de recursos que no produces + puerto (3 si es "
                "2:1 de tu recurso dominante, 1 si es 3:1) − 2 por camino extra − 2 si hay "
                "un rival cerca. Es una fórmula del tablero, no el modelo. Los destinos ya "
                "se marcan en el tablero con su letra y su ruta."
            ),
            "destinos": [
                d.model_dump(exclude={"vertice", "ruta"}) for d in respuesta.destinos
            ],
        }

    def _mi_produccion(self) -> dict:
        if self.peticion.tablero is None:
            return {"error": "No hay tablero cargado."}
        datos = self._resumen_de_partida()
        if datos is None:
            return {"error": "Primero marca tus poblados en el tablero (Mi poblado)."}
        self.fuentes.add("modelo")
        return {
            **datos,
            "numeros_que_pagan": {str(n): c for n, c in datos["numeros_que_pagan"].items()},
            "nota": (
                "Ronda = cada jugador tira una vez; cobras en todas las tiradas. Las "
                "ciudades cobran doble. Rondas estimadas contando el cambio con el banco "
                "o tus puertos para lo que no produces."
            ),
        }

    # --- Apoyo -------------------------------------------------------------

    def _en_partida(self) -> bool:
        """Con dos piezas propias o más, la colocación inicial terminó."""
        return len(self._propios()) + len(self.peticion.ciudades) >= 2

    def _resumen_de_partida(self) -> dict | None:
        """Producción de todas tus piezas (``domain/partida.py``), o None sin piezas."""
        if self.peticion.tablero is None:
            return None
        poblados = [vertice_desde_id(v) for v in self._propios()]
        ciudades = [vertice_desde_id(v) for v in self.peticion.ciudades]
        if not poblados and not ciudades:
            return None
        dominio = tablero_desde_api(self.peticion.tablero.model_dump())
        return partida.resumen(poblados, ciudades, dominio, self.peticion.jugadores)

    def _propios(self) -> list[str]:
        """Los poblados del usuario: todos los marcados, o al menos el primero."""
        if self.peticion.propios:
            return list(self.peticion.propios)
        return [self.peticion.mio] if self.peticion.mio else []

    def _sin_opciones(self) -> dict:
        """Qué decir cuando no hay opciones en pantalla, según el momento."""
        if self._en_partida():
            return {
                "error": "La colocación inicial ya está completa. En partida usa "
                         "mi_produccion (qué produces y qué construir) y "
                         "hacia_donde_expandir (dónde va tu siguiente poblado).",
            }
        return {"error": "Primero hace falta una recomendación en pantalla."}

    @staticmethod
    def _comparar_con_familia(opcion: Opcion, familia: str) -> list[dict] | str:
        """
        Las capacidades de la opción junto al perfil típico de su familia (el centro
        de su grupo en el agrupamiento): así se ve en qué se parece a las demás.
        """
        paquete = modelo.paquete()
        perfil = perfil_de_familia(paquete, familia) if paquete else None
        if perfil is None:
            return "El agrupamiento del modelo no está disponible."
        # +0.0 evita que un -0.0 del centro se imprima con signo.
        return [
            {
                "variable": c,
                "significa": SIGNIFICADO_CAPACIDAD.get(c, c),
                "esta_opcion": round(opcion.variables.get(c, 0), 2) + 0.0,
                "tipico_de_la_familia": round(valor, 2) + 0.0,
            }
            for c, valor in perfil.items()
        ]

    def _plan_de_familia(self, opcion: Opcion, familia: str) -> list[dict]:
        """Pasos en el orden que prioriza la familia, con las rondas estimadas."""
        v = opcion.variables
        ritmo = self._cartas_por_ronda(opcion)
        dominante = max(RECURSOS, key=lambda r: v.get(f"pips_{r}", 0))
        pasos = []
        for paso in PRIORIDAD[familia]:
            if paso == "acumular":
                pasos.append({
                    "que": f"juntar {dominante} y cambiarlo en el puerto",
                    "cartas_por_ronda": ritmo[dominante],
                    "por_que": "es lo que más produces; en su puerto 2:1 vale el doble",
                })
            elif paso == "puerto":
                pasos.append({
                    "que": "llegar a un puerto con caminos",
                    "por_que": f"produces sobre todo {dominante} y sin puerto lo cambias 4:1",
                })
            else:
                pasos.append({
                    "que": paso.replace("_", " de "),
                    "rondas_estimadas": round(v.get(f"turnos_a_{paso}", 0), 1),
                    "puntos_de_victoria": PUNTOS_POR_PIEZA[paso],
                })
        return pasos


    def _opcion_seleccionada(self) -> Opcion | None:
        return self.peticion.opciones[self._seleccionada()] if self.peticion.opciones else None

    def _puertos_seleccionada(self) -> set[str]:
        """Los puertos a los que dan acceso los dos poblados de la opción seleccionada."""
        opcion = self._opcion_seleccionada()
        if opcion is None and self._en_partida():
            datos = self._resumen_de_partida()
            return set(datos["puertos"]) if datos else set()
        if opcion is None or self.peticion.tablero is None:
            return set()
        return {
            v.puerto
            for v in self.peticion.tablero.vertices
            if v.id in opcion.vertices and v.puerto
        }

    @staticmethod
    def _cartas_por_ronda(opcion: Opcion) -> dict[str, float]:
        """
        Cartas esperadas de cada recurso por ronda: pips/36 por cada tirada, y en una
        ronda tiran todos los jugadores (se cobra en todas las tiradas, AGENTS 5.1).
        """
        jugadores = opcion.variables.get("jugadores", 4)
        return {
            r: round(opcion.variables.get(f"pips_{r}", 0) / 36 * jugadores, 3) for r in RECURSOS
        }

    @staticmethod
    def _planear_cambios(sobrante: dict[str, int], necesarios: int, puertos: set[str]) -> list:
        """
        Qué cambios hacer para conseguir `necesarios` cartas, empezando por el recurso
        con mejor tasa. Cada cambio entrega `tasa` cartas iguales por 1 cualquiera.
        """
        disponibles = dict(sobrante)
        cambios = []
        while len(cambios) < necesarios:
            posibles = [
                (_tasa_de_cambio(r, puertos), r)
                for r, n in disponibles.items()
                if n >= _tasa_de_cambio(r, puertos)
            ]
            if not posibles:
                break
            tasa, recurso = min(posibles)
            disponibles[recurso] -= tasa
            if tasa == 4:
                donde = "banco"
            elif tasa == 3:
                donde = "puerto 3:1"
            else:
                donde = f"puerto 2:1 de {recurso}"
            cambios.append(f"entregar {tasa} {recurso} por 1 carta ({donde})")
        return cambios


    def _resolver(self, referencia: dict) -> str | dict:
        """
        'Opción N, poblado K' → id interno del vértice. Si la referencia no existe,
        devuelve un error que dice cuáles son válidas, para que el modelo corrija.
        """
        opciones = self.peticion.opciones
        n, k = referencia.get("opcion"), referencia.get("poblado")
        if not opciones:
            return {"error": "No hay opciones en pantalla a las que referirse."}
        if not (isinstance(n, int) and 1 <= n <= len(opciones)) or k not in (1, 2):
            return {"error": f"Referencia inválida (opción {n}, poblado {k}). Hay "
                             f"{len(opciones)} opciones, cada una con poblado 1 y 2."}
        return opciones[n - 1].vertices[k - 1]

    @staticmethod
    def _bloqueado(vertice: str, ocupados: list[str], propio: str | None) -> bool:
        """Regla de distancia: marcado, o vecino de algo marcado."""
        marcados = [vertice_desde_id(v) for v in [*ocupados, *([propio] if propio else [])]]
        v = vertice_desde_id(vertice)
        return any(v == m or v in TOPOLOGIA.adyacentes[m] for m in marcados)

    def _describir(self, vertice: str) -> str:
        """Un vértice por sus recursos y números, como lo ve el usuario."""
        dominio = tablero_desde_api(self.peticion.tablero.model_dump())
        return describir_vertice(vertice_desde_id(vertice), dominio)

    def _seleccionada(self) -> int:
        return min(self.peticion.elegida, max(len(self.peticion.opciones) - 1, 0))

    @staticmethod
    def _resumir(indice: int, opcion: Opcion) -> dict:
        """Lo que el asistente necesita saber de una opción, sin las 40 variables."""
        v = opcion.variables
        return {
            "numero": indice + 1,
            "familia": opcion.explicacion.titulo,
            "puntos_estimados": opcion.prediccion,
            "pips_por_recurso": {r: v.get(f"pips_{r}", 0) for r in RECURSOS},
            "pips_totales": v.get("pips_totales"),
            "tiene_puerto": bool(v.get("num_puertos", 0)),
            "poblados": opcion.descripciones,
            "resumen": opcion.explicacion.resumen,
            "por_que": opcion.explicacion.porque,
            "haz": opcion.explicacion.haz,
            "evita": opcion.explicacion.evita,
        }
