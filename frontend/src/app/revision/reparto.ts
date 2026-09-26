/**
 * Reparto del juego base, para decir al usuario qué le falta al revisar un tablero.
 *
 * Es una guía para la pantalla de revisión: la autoridad es el backend, que valida
 * el tablero completo al confirmar (`POST /tableros/validar`). Los números salen de
 * `TERRENOS` y `FICHAS` en `backend/app/domain/tablero.py`.
 */
import type { Hexagono, Terreno } from '../api/tipos';

export const TERRENOS_BASE: Record<Terreno, number> = {
  bosque: 4,
  pastos: 4,
  campos: 4,
  colinas: 3,
  montanas: 3,
  desierto: 1,
};

/** Cuántas fichas hay de cada número (el 7 no tiene ficha). */
export const FICHAS_BASE: Record<number, number> = {
  2: 1, 3: 2, 4: 2, 5: 2, 6: 2, 8: 2, 9: 2, 10: 2, 11: 2, 12: 1,
};

export const NUMEROS = Object.keys(FICHAS_BASE).map(Number);

/** Qué recurso produce cada terreno (`RECURSO_DE_TERRENO` en el dominio). */
export const RECURSO_DE_TERRENO: Record<Terreno, Hexagono['recurso']> = {
  bosque: 'madera',
  pastos: 'oveja',
  campos: 'trigo',
  colinas: 'ladrillo',
  montanas: 'mineral',
  desierto: null,
};

export const NOMBRE_TERRENO: Record<Terreno, string> = {
  bosque: 'Bosque',
  pastos: 'Pastos',
  campos: 'Campos',
  colinas: 'Colinas',
  montanas: 'Montañas',
  desierto: 'Desierto',
};

/** Pips de un número: en cuántas de las 36 tiradas sale. 6 − |7 − n|. */
export function pipsDe(numero: number | null | undefined): number {
  return numero ? 6 - Math.abs(7 - numero) : 0;
}

export interface Conteo<K> {
  clave: K;
  hay: number;
  esperado: number;
}

export function conteoTerrenos(hexagonos: Hexagono[]): Conteo<Terreno>[] {
  return (Object.keys(TERRENOS_BASE) as Terreno[]).map((t) => ({
    clave: t,
    hay: hexagonos.filter((h) => h.terreno === t).length,
    esperado: TERRENOS_BASE[t],
  }));
}

export function conteoFichas(hexagonos: Hexagono[]): Conteo<number>[] {
  return NUMEROS.map((n) => ({
    clave: n,
    hay: hexagonos.filter((h) => h.numero === n).length,
    esperado: FICHAS_BASE[n],
  }));
}

/** Los hexágonos que todavía necesitan número: todos menos el desierto. */
export function sinNumero(hexagonos: Hexagono[]): Hexagono[] {
  return hexagonos.filter((h) => h.terreno !== 'desierto' && !h.numero);
}
