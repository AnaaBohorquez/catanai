"""
estrategia.py
=============
Motor de recomendación: convierte un tablero en consejos.

Hace tres cosas encadenadas:

1. Genera las parejas de vértices legales y las puntúa con la regresión.
2. Clasifica cada pareja en una de las cuatro familias de estrategia que salieron
   del agrupamiento.
3. Redacta la explicación en lenguaje natural, usando los números de la propia
   pareja.

La explicación se arma con plantillas y no con un modelo de lenguaje: así es
determinista, no depende de una conexión, y cada frase se puede rastrear hasta el
dato que la genera.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.domain.simulador import parejas_candidatas
from app.domain.tablero import RECURSOS, hexagonos_del_vertice, puerto_del_vertice
from app.domain.variables import variables_de_pareja, pips_por_recurso_del_tablero

RUTA_MODELO = Path(__file__).resolve().parents[3] / "modelos" / "colono.joblib"

#: Nombres legibles de las cuatro familias, y qué aconsejan.
ESTRATEGIAS = {
    "expansion": {
        "nombre": "Expansión",
        "resumen": "Creces a lo ancho: más poblados y la carta de camino más largo.",
        "haz": "Tiende caminos desde el primer turno y ocupa los vértices libres antes que nadie.",
        "evita": "No te obsesiones con subir a ciudad temprano; tu ventaja es el ritmo.",
    },
    "ciudades": {
        "nombre": "Ciudades y desarrollo",
        "resumen": "Creces hacia arriba: subes poblados a ciudad y compras cartas.",
        "haz": "Prioriza la primera ciudad; duplica producción y te acerca al ejército mayor.",
        "evita": "Gastar de más en caminos: tu espacio importa menos que tu producción.",
    },
    "puerto": {
        "nombre": "Puerto y conversión",
        "resumen": "Produces mucho de un recurso y lo cambias a mitad de precio.",
        "haz": "Acumula tu recurso dominante y conviértelo 2:1 en lo que te falte.",
        "evita": "Depender del comercio con otros jugadores: tu puerto ya te da independencia.",
    },
    "desequilibrada": {
        "nombre": "Producción desequilibrada",
        "resumen": "Recibes cartas, pero de pocos tipos y difíciles de gastar.",
        "haz": "Busca un puerto cuanto antes, o cambia de pareja si todavía puedes.",
        "evita": "Confiarte por los pips altos: producir no es lo mismo que construir.",
    },
}


def cargar_modelo(ruta: Path | str = RUTA_MODELO) -> dict:
    """Carga el paquete guardado por el notebook de modelado."""
    paquete = joblib.load(ruta)
    paquete["nombres_grupo"] = _nombrar_grupos(paquete)
    return paquete


def _nombrar_grupos(paquete: dict) -> dict[int, str]:
    """
    Asigna un nombre a cada grupo del agrupamiento.

    Los números de grupo que devuelve KMeans son arbitrarios, así que no se pueden
    codificar a mano: hay que deducir qué es cada uno mirando su centro. Se hace
    por eliminación, de la familia más distinguible a la menos.
    """
    capacidades = paquete["capacidades"]
    centros = paquete["escalador_capacidades"].inverse_transform(
        paquete["agrupamiento"].cluster_centers_
    )
    perfil = {i: dict(zip(capacidades, fila)) for i, fila in enumerate(centros)}

    nombres, libres = {}, set(perfil)

    # El de puerto es inconfundible: es el único con puerto_alineado alto.
    i = max(libres, key=lambda g: perfil[g]["puerto_alineado"])
    nombres[i] = "puerto"
    libres.remove(i)

    # Entre los que quedan, el de más par_camino es el de expansión.
    i = max(libres, key=lambda g: perfil[g]["par_camino"])
    nombres[i] = "expansion"
    libres.remove(i)

    # El de más trio_desarrollo es el de ciudades y cartas.
    i = max(libres, key=lambda g: perfil[g]["trio_desarrollo"])
    nombres[i] = "ciudades"
    libres.remove(i)

    # El que sobra es el desequilibrado.
    for i in libres:
        nombres[i] = "desequilibrada"
    return nombres


def perfil_de_familia(paquete: dict, familia: str) -> dict[str, float] | None:
    """
    El perfil típico de una familia: el centro de su grupo en el agrupamiento, en
    las unidades originales de cada capacidad. Sirve para explicar por qué una
    opción es de esa familia comparando sus variables con las del grupo.
    """
    centros = paquete["escalador_capacidades"].inverse_transform(
        paquete["agrupamiento"].cluster_centers_
    )
    capacidades = paquete["capacidades"]
    for i, nombre in paquete["nombres_grupo"].items():
        if nombre == familia:
            return {c: float(v) for c, v in zip(capacidades, centros[i], strict=True)}
    return None


def recomendar(
    tablero: dict,
    paquete: dict,
    ocupados: set | None = None,
    jugadores: int = 4,
    cuantas: int = 3,
    diversificar: bool = True,
    mio: frozenset | None = None,
) -> list[dict]:
    """
    Devuelve las mejores parejas de vértices para este tablero.

    Parameters
    ----------
    tablero : dict
        Tablero de ``tablero.generar_tablero`` o construido por el usuario.
    paquete : dict
        Lo que devuelve ``cargar_modelo()``.
    ocupados : set, opcional
        Vértices ya tomados por otros jugadores. Sus vecinos quedan bloqueados
        por la regla de distancia mínima de dos.
    jugadores : int
        Cuántos juegan. Cambia el ritmo de producción y el espacio disponible.
    cuantas : int
        Cuántas recomendaciones devolver.
    diversificar : bool
        Si es True, después de la mejor pareja se buscan las mejores de OTRAS
        familias de estrategia. Tres opciones de la misma familia se parecen
        demasiado entre sí y no ayudan a decidir; con familias distintas el
        usuario elige la forma de jugar que prefiere.
    mio : frozenset, opcional
        El primer poblado del jugador, si ya lo colocó. Con esto la búsqueda deja
        de ser de parejas y pasa a ser del mejor compañero para ese vértice, que
        es la situación real cuando entre tu primera y tu segunda colocación
        juegan los demás.

    Returns
    -------
    list of dict
        Ordenadas de mejor a peor. Cada una trae los vértices, la predicción, la
        estrategia y su explicación.
    """
    parejas = parejas_candidatas(tablero, ocupados=ocupados, obligatorio=mio)
    if not parejas:
        return []

    pips_tablero = pips_por_recurso_del_tablero(tablero)
    variables = [
        variables_de_pareja(v1, v2, tablero, jugadores, pips_tablero)
        for v1, v2 in parejas
    ]

    # Se pasan como DataFrame con los nombres de columna: el modelo se ajustó así,
    # y con un array suelto sklearn avisa de que faltan los nombres.
    matriz = pd.DataFrame(variables)[paquete["variables"]]
    predicciones = paquete["modelo"].predict(matriz)

    capacidades = pd.DataFrame(variables)[paquete["capacidades"]]
    grupos = paquete["agrupamiento"].predict(
        paquete["escalador_capacidades"].transform(capacidades)
    )

    orden = np.argsort(predicciones)[::-1]
    mejores = _elegir(orden, grupos, paquete["nombres_grupo"], cuantas, diversificar)

    return [
        {
            "vertices": parejas[i],
            "prediccion": float(predicciones[i]),
            "estrategia": paquete["nombres_grupo"][int(grupos[i])],
            "variables": variables[i],
            "explicacion": explicar(parejas[i], variables[i],
                                    paquete["nombres_grupo"][int(grupos[i])], tablero),
        }
        for i in mejores
    ]


#: Familias que no se ofrecen como alternativa. La desequilibrada se explica a sí
#: misma con "cambia de pareja si todavía puedes": proponerla como opción 2 o 3
#: contradice a la app. Sí se muestra si es la mejor de todas, porque ocultarla ahí
#: falsearía el ranking. En 30 tableros aparecía como alternativa en 6.
SOLO_SI_ES_LA_MEJOR = {"desequilibrada"}


def _elegir(orden, grupos, nombres, cuantas: int, diversificar: bool) -> list[int]:
    """
    Escoge qué parejas mostrar.

    Siempre entra la mejor. Después, si se pide diversificar, se prefieren las
    mejores de familias de estrategia que no hayan salido todavía, sin contar las
    de ``SOLO_SI_ES_LA_MEJOR``. Cuando se acaban las familias se completa con las
    siguientes mejores, y las excluidas solo entran si aun así faltan parejas.
    """
    if not diversificar:
        return list(orden[:cuantas])

    def familia(i) -> str:
        return nombres[int(grupos[i])]

    elegidas = [orden[0]]
    vistas = {familia(orden[0])}
    for i in orden[1:]:
        if len(elegidas) == cuantas:
            return elegidas
        if familia(i) not in vistas and familia(i) not in SOLO_SI_ES_LA_MEJOR:
            elegidas.append(i)
            vistas.add(familia(i))

    for admitir_excluidas in (False, True):
        for i in orden:
            if len(elegidas) == cuantas:
                return elegidas
            if i in elegidas:
                continue
            if admitir_excluidas or familia(i) not in SOLO_SI_ES_LA_MEJOR:
                elegidas.append(i)
    return elegidas


def explicar(pareja: tuple, v: dict, estrategia: str, tablero: dict) -> dict:
    """
    Redacta la explicación de una recomendación.

    Returns
    -------
    dict
        Con las llaves ``titulo``, ``produccion``, ``porque``, ``haz`` y ``evita``.
    """
    ficha = ESTRATEGIAS[estrategia]

    produccion = {r: v[f"pips_{r}"] for r in RECURSOS}
    ordenados = sorted(produccion.items(), key=lambda x: -x[1])
    fuertes = [r for r, p in ordenados if p > 0][:3]
    ausentes = [r for r, p in produccion.items() if p == 0]

    porque = []
    if v["par_camino"] >= 3:
        porque.append(
            "tienes madera y ladrillo a la vez, que es lo que permite construir "
            "caminos y poblados sin depender del comercio"
        )
    if v["par_ciudad"] >= 1:
        porque.append("produces trigo y mineral en proporción suficiente para subir a ciudad")
    if v["trio_desarrollo"] >= 2:
        porque.append(
            "cubres trigo, oveja y mineral, la combinación de las cartas de desarrollo"
        )
    if v["puerto_alineado"]:
        dominante = ordenados[0][0]
        porque.append(
            f"el puerto 2:1 es justo de {dominante}, que es lo que más produces: "
            "cambias a mitad de precio"
        )
    elif v["puerto_generico"]:
        porque.append("tienes puerto 3:1, así que conviertes excedentes más barato que en el banco")
    if v["desequilibrio"] > 0.45 and not v["puerto_alineado"]:
        porque.append(
            "la producción está concentrada en pocos recursos, así que vas a "
            "necesitar comerciar para gastar lo que recibes"
        )
    if v["vertices_expansion_2"] >= 6:
        porque.append("te queda bastante espacio libre alrededor para tu tercer poblado")
    if not porque:
        porque.append("la producción está repartida sin una combinación dominante")

    texto_produccion = ", ".join(f"{r} {int(produccion[r])}" for r in fuertes)
    if ausentes:
        texto_produccion += f". No produces {', '.join(ausentes)}"

    return {
        "titulo": ficha["nombre"],
        "resumen": ficha["resumen"],
        "produccion": texto_produccion,
        "porque": porque,
        "haz": ficha["haz"],
        "evita": ficha["evita"],
    }


def describir_vertice(vertice: frozenset, tablero: dict) -> str:
    """Texto corto con lo que toca un vértice, para mostrarlo en la interfaz."""
    partes = []
    for h in hexagonos_del_vertice(vertice, tablero):
        recurso = tablero["recursos"][h] or "desierto"
        numero = tablero["numeros"].get(h)
        partes.append(f"{recurso} {numero}" if numero else recurso)
    puerto = puerto_del_vertice(vertice, tablero)
    texto = " · ".join(partes)
    return f"{texto} · puerto {puerto}" if puerto else texto
