/**
 * Aristas de la costa y edición de los puertos en la pantalla de revisión.
 *
 * Misma definición que el dominio (`backend/app/domain/puertos.py`): una arista es
 * de costa si, de los dos hexágonos que comparten sus vértices, exactamente uno es
 * tierra. Se ordenan alrededor del tablero en sentido horario desde arriba.
 */
import type { Puerto, Tablero } from '../api/tipos';
import { centroVertice } from '../tablero/geometria';

/** Aristas que avanza la plantilla por cada giro de 60° (30 aristas / 6 lados). */
const ARISTAS_POR_GIRO = 5;

/** Una arista como la pareja ordenada de sus vértices, igual que en la API. */
export type Arista = [string, string];

export function clave(arista: readonly string[]): string {
  return [...arista].sort().join('~');
}

export function aristasDeCosta(tablero: Tablero): Arista[] {
  const tierra = new Set(tablero.hexagonos.map((h) => h.id));
  const costa = tablero.aristas
    .map((a) => [...a.vertices].sort() as Arista)
    .filter(([a, b]) => {
      const deA = new Set(a.split('|'));
      const compartidos = b.split('|').filter((h) => deA.has(h));
      return compartidos.filter((h) => tierra.has(h)).length === 1;
    });
  const angulo = ([a, b]: Arista) => {
    const pa = centroVertice(a, 1);
    const pb = centroVertice(b, 1);
    const x = (pa.x + pb.x) / 2;
    const y = (pa.y + pb.y) / 2;
    // 0 arriba y luego en sentido horario, con el eje y hacia abajo como en pantalla.
    return (Math.atan2(x, -y) + 2 * Math.PI) % (2 * Math.PI);
  };
  return costa.sort((p, q) => angulo(p) - angulo(q));
}

/** Rota todos los puertos 60° en sentido horario a lo largo de la costa. */
export function girarPuertos(tablero: Tablero): Puerto[] {
  const costa = aristasDeCosta(tablero);
  const indice = new Map(costa.map((a, i) => [clave(a), i]));
  return tablero.puertos.map((p) => {
    const i = indice.get(clave(p.vertices));
    if (i === undefined) return p; // un puerto fuera de la costa se deja donde está
    return { ...p, vertices: costa[(i + ARISTAS_POR_GIRO) % costa.length] };
  });
}

/**
 * Aristas de costa a las que se puede mover el puerto `indice`: libres y sin
 * compartir vértice con los otros puertos.
 */
export function destinosPosibles(tablero: Tablero, indice: number): Arista[] {
  const otros = tablero.puertos.filter((_, i) => i !== indice);
  const usados = new Set(otros.flatMap((p) => p.vertices));
  return aristasDeCosta(tablero).filter(([a, b]) => !usados.has(a) && !usados.has(b));
}
