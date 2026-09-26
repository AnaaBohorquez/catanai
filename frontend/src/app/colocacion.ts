/**
 * Estado de la colocación en curso: qué vértices marcó el usuario en el tablero.
 *
 * Las marcas son la única fuente de verdad de lo ocupado. De ellas se derivan el
 * `mio` y los `ocupados` que recibe `/recomendar`, lo que ve el chat y lo que queda
 * bloqueado por la regla de distancia.
 */

/** Un vértice marcado: el poblado del usuario o el de un rival. */
export type Marca = 'propio' | 'rival';

/** Id de vértice → marca. Un vértice sin entrada está libre. */
export type Marcas = Readonly<Record<string, Marca>>;

/** Qué hace un toque sobre el tablero. `null`: no se está marcando. */
export type ModoMarcado = 'propio' | 'rival' | 'borrar' | null;

/** En la colocación inicial cada jugador pone dos poblados. */
export const MAX_PROPIOS = 2;

export function propios(marcas: Marcas): string[] {
  return Object.keys(marcas).filter((v) => marcas[v] === 'propio');
}

export function rivales(marcas: Marcas): string[] {
  return Object.keys(marcas).filter((v) => marcas[v] === 'rival');
}

/**
 * Una firma estable de las marcas y los jugadores. Si no cambió, las opciones en
 * pantalla ya corresponden a este estado y no hay que recalcular.
 */
export function firma(marcas: Marcas, jugadores: number): string {
  const partes = Object.keys(marcas)
    .sort()
    .map((v) => `${v}=${marcas[v]}`);
  return `${jugadores}#${partes.join(';')}`;
}
