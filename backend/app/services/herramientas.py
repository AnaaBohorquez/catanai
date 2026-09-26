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
from app.domain.reglas import buscar_reglas, reglas_verificadas
from app.domain.tablero import COSTOS, PIPS, RECURSOS
from app.domain.variables import _tasa_de_cambio, pips_por_recurso_del_tablero
from app.schemas.api import Opcion, PeticionChat, PeticionRecomendar
from app.services.recomendacion import ModeloNoDisponible, calcular
from app.services.serializers import tablero_desde_api

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
            "Pide al modelo una recomendación nueva para el mismo tablero, por ejemplo "
            "si otro jugador ocupó un vértice o si el usuario ya colocó su primer "
            "poblado. Los vértices se identifican con los ids de ver_resultados_actuales."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "ocupados": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Vértices que ya tomaron otros jugadores",
                },
                "mio": {
                    "type": ["string", "null"],
                    "description": "Vértice del primer poblado del usuario, si ya lo colocó",
                },
                "jugadores": {
                    "type": ["integer", "null"],
                    "description": "3 o 4; null para conservar el número actual",
                },
            },
            "required": ["ocupados", "mio", "jugadores"],
            "additionalProperties": False,
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
]

DEFINICIONES = DEFINICIONES + DEFINICIONES_EXPERTO


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
            return {"opciones": [], "nota": "Aún no hay una recomendación en pantalla."}
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
        self, ocupados: list[str], mio: str | None = None, jugadores: int | None = None
    ) -> dict:
        if self.peticion.tablero is None:
            return {"error": "No hay tablero cargado."}
        actuales = self.peticion.opciones
        # El número de jugadores viaja dentro de las variables de cada opción.
        por_defecto = int(actuales[0].variables.get("jugadores", 4)) if actuales else 4
        try:
            respuesta = calcular(
                PeticionRecomendar(
                    tablero=self.peticion.tablero,
                    jugadores=jugadores or por_defecto,
                    ocupados=ocupados,
                    mio=mio,
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
        return {
            "nota": "Estas opciones ya se muestran en pantalla y reemplazan a las anteriores.",
            "opciones": [self._resumir(i, o) for i, o in enumerate(respuesta.opciones)],
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
        if opcion is None:
            return {"error": "Primero hace falta una recomendación en pantalla."}
        self.fuentes.add("modelo")
        puertos = self._puertos_seleccionada()
        ritmo = self._cartas_por_ronda(opcion)
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
            "pips_propios": opcion.variables.get(f"pips_{recurso}", 0),
            "cartas_por_ronda_produciendo": propio,
            "rondas_por_carta": round(1 / propio, 1) if propio > 0 else None,
            "mejores_cambios": fuentes_de_cambio[:2],
            "puertos_de_la_opcion": sorted(puertos) or ["ninguno"],
            "nota": (
                "Ronda = cada jugador tira una vez. También puedes comerciar con otros "
                "jugadores."
            ),
        }

    def _plan_de_construccion(self) -> dict:
        opcion = self._opcion_seleccionada()
        if opcion is None:
            return {"error": "Primero hace falta una recomendación en pantalla."}
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

    # --- Apoyo -------------------------------------------------------------

    def _opcion_seleccionada(self) -> Opcion | None:
        return self.peticion.opciones[self._seleccionada()] if self.peticion.opciones else None

    def _puertos_seleccionada(self) -> set[str]:
        """Los puertos a los que dan acceso los dos poblados de la opción seleccionada."""
        opcion = self._opcion_seleccionada()
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
            "vertices": opcion.vertices,
            "resumen": opcion.explicacion.resumen,
            "por_que": opcion.explicacion.porque,
            "haz": opcion.explicacion.haz,
            "evita": opcion.explicacion.evita,
        }
