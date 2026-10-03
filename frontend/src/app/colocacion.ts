/**
 * Estado de la partida marcada en el tablero: qué vértices marcó el usuario.
 *
 * Las marcas son la única fuente de verdad de lo ocupado. De ellas se derivan el
 * `mio` y los `ocupados` que recibe `/recomendar`, lo que ve el chat y lo que queda
 * bloqueado por la regla de distancia.
 */

/** Un vértice marcado: un poblado o una ciudad del usuario, o una pieza de un rival. */
export type Marca = 'propio' | 'ciudad' | 'rival';

/** Id de vértice → marca. Un vértice sin entrada está libre. */
export type Marcas = Readonly<Record<string, Marca>>;

/** Qué hace un toque sobre el tablero. `null`: no se está marcando. */
export type ModoMarcado = 'propio' | 'ciudad' | 'rival' | 'borrar' | null;

/** En la colocación inicial cada jugador pone dos poblados; después, la partida. */
export const PIEZAS_INICIALES = 2;
/** Piezas de cada jugador en el juego base. */
export const MAX_POBLADOS = 5;
export const MAX_CIUDADES = 4;

export function propios(marcas: Marcas): string[] {
  return Object.keys(marcas).filter((v) => marcas[v] === 'propio');
}

export function ciudades(marcas: Marcas): string[] {
  return Object.keys(marcas).filter((v) => marcas[v] === 'ciudad');
}

export function rivales(marcas: Marcas): string[] {
  return Object.keys(marcas).filter((v) => marcas[v] === 'rival');
}

/** Lo que produce un toque: las marcas nuevas, o un aviso si no se puede. */
export type Toque = { marcas: Marcas } | { aviso: string } | null;

/**
 * Aplica un toque sobre el vértice `id` en el modo actual, con las reglas del juego:
 * la distancia entre poblados, el máximo de piezas y que una ciudad solo sale de un
 * poblado tuyo.
 */
export function tocar(
  marcas: Marcas,
  id: string,
  modo: ModoMarcado,
  bloqueados: ReadonlySet<string>,
): Toque {
  const actual = marcas[id];
  const sin = () => {
    const { [id]: _, ...resto } = marcas;
    return resto;
  };
  if (modo === null) return null;

  if (modo === 'borrar') return actual ? { marcas: sin() } : null;

  if (modo === 'ciudad') {
    if (actual === 'ciudad') return { marcas: { ...marcas, [id]: 'propio' } };
    if (actual !== 'propio') return { aviso: 'Para una ciudad, toca uno de tus poblados.' };
    if (ciudades(marcas).length >= MAX_CIUDADES) {
      return { aviso: `Ya tienes tus ${MAX_CIUDADES} ciudades.` };
    }
    return { marcas: { ...marcas, [id]: 'ciudad' } };
  }

  if (actual === modo) return { marcas: sin() };
  if (!actual && bloqueados.has(id)) {
    return { aviso: 'Ese vértice está junto a otro poblado (regla de distancia).' };
  }
  if (modo === 'propio' && actual !== 'ciudad' && propios(marcas).length >= MAX_POBLADOS) {
    return { aviso: `Ya tienes tus ${MAX_POBLADOS} poblados: sube uno a ciudad para liberar otro.` };
  }
  return { marcas: { ...marcas, [id]: modo } };
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
