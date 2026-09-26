"""
generar_dataset.py
==================
Construye el dataset de entrenamiento: una fila por pareja candidata, con sus
40 variables y los puntos simulados como variable objetivo.

Uso
---
    python -m scripts.generar_dataset                      # 200 tableros, ~25 min
    python -m scripts.generar_dataset --tableros 20        # prueba rápida, ~3 min
    python -m scripts.generar_dataset --procesos 4         # en paralelo

El resultado va a ``data/processed/parejas.csv``.

Notas
-----
- El archivo se escribe de forma incremental: si el proceso se corta, lo ya
  calculado queda guardado y se puede continuar con ``--continuar``.
- Cada tablero recibe 3 o 4 jugadores de forma alterna, para que la variable
  ``jugadores`` tenga variación.
- La columna ``tablero_id`` es imprescindible: al entrenar hay que partir los
  datos POR TABLERO y no por fila. Las ~193 parejas de un mismo tablero
  comparten información, y si caen unas en entrenamiento y otras en prueba la
  métrica sale inflada.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.simulador import parejas_candidatas, simular_pareja  # noqa: E402
from app.domain.tablero import generar_tablero  # noqa: E402
from app.domain.variables import variables_de_parejas  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "processed" / "parejas.csv"


def procesar_tablero(argumentos: tuple) -> list[dict]:
    """
    Calcula todas las filas de un tablero.

    Está fuera de ``main`` y recibe una única tupla para poder usarse con
    ``multiprocessing.Pool.imap``.

    Parameters
    ----------
    argumentos : tuple
        ``(semilla, partidas)``.

    Returns
    -------
    list of dict
        Una fila por pareja candidata, con variables y objetivo.
    """
    semilla, partidas = argumentos

    tablero = generar_tablero(semilla=semilla)
    # Se alterna para que la variable `jugadores` tenga variación.
    jugadores = 3 if semilla % 2 else 4
    parejas = parejas_candidatas(tablero)
    filas = variables_de_parejas(tablero, parejas, jugadores)

    for fila, (v1, v2) in zip(filas, parejas):
        fila["tablero_id"] = semilla
        fila["puntos"] = simular_pareja(
            tablero, v1, v2, partidas=partidas, jugadores=jugadores, semilla=semilla
        )
    return filas


def semillas_ya_hechas(ruta: Path) -> set[int]:
    """Qué tableros están ya en el CSV, para poder continuar una corrida cortada."""
    if not ruta.exists():
        return set()
    with ruta.open(newline="", encoding="utf-8") as f:
        return {int(fila["tablero_id"]) for fila in csv.DictReader(f)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tableros", type=int, default=200,
                        help="cuántos tableros generar (200 ≈ 25 min)")
    parser.add_argument("--partidas", type=int, default=40,
                        help="mini-partidas por pareja; 40 da un ruido de ±0.11 puntos")
    parser.add_argument("--procesos", type=int, default=1,
                        help="procesos en paralelo; 1 desactiva el paralelismo")
    parser.add_argument("--salida", type=Path, default=SALIDA)
    parser.add_argument("--continuar", action="store_true",
                        help="añadir al CSV existente en vez de empezar de cero")
    args = parser.parse_args()

    args.salida.parent.mkdir(parents=True, exist_ok=True)

    hechas = semillas_ya_hechas(args.salida) if args.continuar else set()
    pendientes = [s for s in range(args.tableros) if s not in hechas]

    if not pendientes:
        print("No hay tableros pendientes. Nada que hacer.")
        return

    if hechas:
        print(f"Continuando: {len(hechas)} tableros ya hechos, {len(pendientes)} pendientes.")
    print(f"Generando {len(pendientes)} tableros x {args.partidas} partidas por pareja")
    print(f"Salida: {args.salida}\n")

    tareas = [(s, args.partidas) for s in pendientes]
    modo = "a" if hechas else "w"
    escritor = None
    total_filas = len(hechas) * 0
    inicio = time.perf_counter()

    with args.salida.open(modo, newline="", encoding="utf-8") as f:
        if args.procesos > 1:
            from multiprocessing import Pool
            with Pool(args.procesos) as pool:
                resultados = pool.imap_unordered(procesar_tablero, tareas)
                escritor, total_filas = _consumir(
                    resultados, f, escritor, total_filas, len(tareas), inicio, bool(hechas)
                )
        else:
            resultados = (procesar_tablero(t) for t in tareas)
            escritor, total_filas = _consumir(
                resultados, f, escritor, total_filas, len(tareas), inicio, bool(hechas)
            )

    duracion = time.perf_counter() - inicio
    print(f"\n\nListo: {total_filas} filas nuevas en {duracion / 60:.1f} min")
    print(f"Archivo: {args.salida}")
    print(f"Tamaño: {os.path.getsize(args.salida) / 1e6:.1f} MB")


def _consumir(resultados, archivo, escritor, total_filas, total_tareas, inicio, ya_habia):
    """Escribe las filas conforme van llegando y muestra el avance."""
    for i, filas in enumerate(resultados, 1):
        if escritor is None:
            columnas = ["tablero_id", "pareja_id", "puntos"] + [
                c for c in filas[0] if c not in ("tablero_id", "pareja_id", "puntos")
            ]
            escritor = csv.DictWriter(archivo, fieldnames=columnas)
            if not ya_habia:
                escritor.writeheader()
        escritor.writerows(filas)
        archivo.flush()
        total_filas += len(filas)

        transcurrido = time.perf_counter() - inicio
        restante = transcurrido / i * (total_tareas - i)
        print(
            f"\r  tablero {i}/{total_tareas} | {total_filas} filas | "
            f"faltan {restante / 60:4.1f} min",
            end="", flush=True,
        )
    return escritor, total_filas


if __name__ == "__main__":
    main()
