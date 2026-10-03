"""
Hacia dónde crecer, del tablero de la API a los destinos con su explicación.

Lo usan el endpoint ``/expansion`` y la herramienta ``hacia_donde_expandir`` del
chat, igual que ``services/recomendacion.py`` con la recomendación inicial.
"""

from __future__ import annotations

from app.core.errors import ErrorDeDominio
from app.domain.expansion import destinos_de_expansion, verificar_expansion
from app.schemas.api import Destino, PeticionExpansion, RespuestaExpansion
from app.services.recomendador import describir_vertice
from app.services.serializers import id_vertice, tablero_desde_api, vertice_desde_id

LETRAS = "ABC"


def calcular(peticion: PeticionExpansion) -> RespuestaExpansion:
    """
    Los mejores vértices para el siguiente poblado del usuario.

    Raises
    ------
    ErrorDeDominio
        Si no hay poblados propios o algún vértice no existe.
    """
    if not peticion.propios and not peticion.ciudades:
        raise ErrorDeDominio(
            "Primero marca tus poblados",
            "Hace falta saber dónde están tus poblados para calcular hacia dónde crecer.",
        )
    tablero = tablero_desde_api(peticion.tablero.model_dump())
    try:
        propios = [vertice_desde_id(v) for v in peticion.propios]
        ciudades = [vertice_desde_id(v) for v in peticion.ciudades]
        rivales = [vertice_desde_id(v) for v in peticion.ocupados]
    except KeyError as error:
        raise ErrorDeDominio("Identificador de vértice desconocido", str(error)) from error

    destinos = destinos_de_expansion(
        tablero, propios, rivales,
        max_caminos=peticion.max_caminos, cuantos=len(LETRAS), ciudades=ciudades,
    )
    verificar_expansion(destinos, [*propios, *ciudades], rivales)
    return RespuestaExpansion(
        destinos=[
            Destino(
                letra=LETRAS[i],
                vertice=id_vertice(d["vertice"]),
                descripcion=describir_vertice(d["vertice"], tablero),
                desde=describir_vertice(d["ruta"][0], tablero),
                caminos=d["caminos"],
                ruta=[id_vertice(v) for v in d["ruta"]],
                pips=d["pips"],
                recursos_nuevos=d["recursos_nuevos"],
                puerto=d["puerto"],
                riesgo_rival=d["riesgo_rival"],
                puntaje=d["puntaje"],
                razones=razones(d),
            )
            for i, d in enumerate(destinos)
        ]
    )


def razones(destino: dict) -> list[str]:
    """Cada término de la fórmula que pesó, en palabras de jugador."""
    salida = [f"suma {destino['pips']} pips de producción"]
    if destino["recursos_nuevos"]:
        salida.append(
            f"te da {', '.join(destino['recursos_nuevos'])}, que tus poblados no producen"
        )
    if destino["puerto_dominante"]:
        salida.append(
            f"tiene puerto 2:1 de {destino['puerto']}, lo que más produces: lo cambias a "
            "mitad de precio"
        )
    elif destino["puerto"] == "3:1":
        salida.append("tiene puerto 3:1 para cambiar excedentes")
    salida.append(
        f"está a {destino['caminos']} caminos"
        + (" (el mínimo posible)" if destino["caminos"] == 2 else "")
    )
    if destino["riesgo_rival"]:
        salida.append("hay un rival cerca: puede ganarte el vértice, ve rápido")
    return salida
