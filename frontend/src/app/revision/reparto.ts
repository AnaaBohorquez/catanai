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

/** Lo que la visión consideró posible para un hexágono, del más al menos probable. */
export interface Opciones {
  numeros: number[];
  terrenos: Terreno[];
}

/** El tablero después de reacomodar, y qué se cambió solo (para decírselo al usuario). */
export interface Reacomodo {
  hexagonos: Hexagono[];
  cambios: string[];
}

/**
 * Tras corregir el hexágono `id`, deja el reparto cuadrado moviendo otra lectura.
 *
 * Si el usuario pone un 9 y ya había dos, el otro 9 que no ha revisado (y del que la
 * visión estaba menos segura) pasa a su siguiente opción que siga libre. Lo mismo con
 * los terrenos, y el número que queda libre va a la ficha que se quedó sin él. Así una
 * corrección arregla también la ficha con la que se había confundido, sin tocarla.
 * Solo se mueven hexágonos leídos por la foto (con opciones) y no revisados a mano.
 */
export function reacomodar(
  hexagonos: Hexagono[],
  id: string,
  revisados: ReadonlySet<string>,
  opciones: Readonly<Record<string, Opciones>>,
): Reacomodo {
  const hs = hexagonos.map((h) => ({ ...h }));
  const cambios: string[] = [];
  const editado = hs.find((h) => h.id === id);
  if (!editado) return { hexagonos: hs, cambios };

  const movible = (h: Hexagono) => h.id !== id && !revisados.has(h.id) && !!opciones[h.id];

  // 1. Terreno: si ahora sobra uno, otro hexágono de ese terreno pasa a su siguiente opción.
  const t = editado.terreno;
  if (hs.filter((h) => h.terreno === t).length > TERRENOS_BASE[t]) {
    const otro = menosSeguro(hs.filter((h) => h.terreno === t && movible(h)), (h) =>
      opciones[h.id].terrenos.indexOf(t),
    );
    if (otro) {
      const libres = (Object.keys(TERRENOS_BASE) as Terreno[]).filter(
        (x) => hs.filter((h) => h.terreno === x).length < TERRENOS_BASE[x],
      );
      const nuevo = opciones[otro.id].terrenos.find((x) => libres.includes(x)) ?? libres[0];
      if (nuevo) {
        cambios.push(`${NOMBRE_TERRENO[t]} → ${NOMBRE_TERRENO[nuevo]}`);
        otro.terreno = nuevo;
        otro.recurso = RECURSO_DE_TERRENO[nuevo];
        if (nuevo === 'desierto') {
          otro.numero = null;
          otro.pips = 0;
        }
      }
    }
  }

  // 2. Número: si ahora sobra uno, otra ficha con ese número pasa a su siguiente opción.
  const n = editado.numero;
  if (n && hs.filter((h) => h.numero === n).length > FICHAS_BASE[n]) {
    const otro = menosSeguro(hs.filter((h) => h.numero === n && movible(h)), (h) =>
      opciones[h.id].numeros.indexOf(n),
    );
    if (otro) {
      otro.numero = null;
      otro.pips = 0;
    }
  }

  // 3. Las fichas que se quedaron sin número reciben uno de los que faltan, en el
  //    orden de preferencia de su lectura.
  for (const h of hs) {
    if (h.terreno === 'desierto' || h.numero || !opciones[h.id] || h.id === id) continue;
    const faltan = NUMEROS.filter(
      (x) => hs.filter((o) => o.numero === x).length < FICHAS_BASE[x],
    );
    const nuevo = opciones[h.id].numeros.find((x) => faltan.includes(x)) ?? faltan[0];
    if (nuevo) {
      const antes = hexagonos.find((o) => o.id === h.id)?.numero;
      h.numero = nuevo;
      h.pips = pipsDe(nuevo);
      if (antes !== nuevo) cambios.push(`${antes ?? 'sin número'} → ${nuevo}`);
    }
  }
  return { hexagonos: hs, cambios };
}

/** El candidato cuya etiqueta actual la visión puso más abajo en su lista. */
function menosSeguro(candidatos: Hexagono[], rango: (h: Hexagono) => number): Hexagono | null {
  return candidatos.reduce<Hexagono | null>(
    (peor, h) => (peor === null || rango(h) > rango(peor) ? h : peor),
    null,
  );
}
