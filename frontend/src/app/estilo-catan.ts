/**
 * Colores e íconos de Catan que comparten el tablero, las cartas y el chat.
 *
 * Viven en un solo lugar para que el trigo del tablero sea el mismo amarillo que
 * la barra de trigo de una carta, y el "1" dibujado sobre el tablero tenga el
 * color de la medalla de la opción 1.
 */
import type { Terreno } from './api/tipos';

export const RECURSOS = ['madera', 'ladrillo', 'trigo', 'oveja', 'mineral'] as const;
export type Recurso = (typeof RECURSOS)[number];

export const COLOR_TERRENO: Record<Terreno, string> = {
  bosque: '#2f6b3a',
  pastos: '#8cc265',
  campos: '#e9c547',
  colinas: '#c8643b',
  montanas: '#8d8f96',
  desierto: '#e3d3a4',
};

/** Cada recurso con el color del terreno que lo produce. */
export const COLOR_RECURSO: Record<Recurso, string> = {
  madera: COLOR_TERRENO.bosque,
  ladrillo: COLOR_TERRENO.colinas,
  trigo: COLOR_TERRENO.campos,
  oveja: COLOR_TERRENO.pastos,
  mineral: COLOR_TERRENO.montanas,
};

export const ICONO_RECURSO: Record<Recurso, string> = {
  madera: '🌲',
  ladrillo: '🧱',
  trigo: '🌾',
  oveja: '🐑',
  mineral: '⛰️',
};

/** Las claves son las familias que devuelve el backend en `opcion.estrategia`. */
export const ICONO_ESTRATEGIA: Record<string, string> = {
  expansion: '🛤️',
  ciudades: '🏰',
  puerto: '⚓',
  desequilibrada: '⚖️',
};

/**
 * Color de cada opción (1, 2, 3): oro, plata y bronce, como sus medallas. Se usa
 * en las marcas del tablero y en las fichas del asistente.
 */
export const COLOR_MEDALLA = ['#c9971c', '#8f9aa6', '#a8683a'];

export const MEDALLA = ['🥇', '🥈', '🥉'];

/** El único color de acción de la interfaz: botones, selección y foco. */
export const COLOR_ACCION = '#b5532b';
