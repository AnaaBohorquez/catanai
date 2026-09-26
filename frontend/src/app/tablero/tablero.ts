import { Component, computed, input, output } from '@angular/core';

import type { Opcion, Tablero } from '../api/tipos';
import { COLOR_MEDALLA, COLOR_RECURSO, COLOR_TERRENO, type Recurso } from '../estilo-catan';
import {
  Punto,
  centroHex,
  centroVertice,
  esquinasHex,
  leerCoordenada,
  posicionPuerto,
  puntosPips,
} from './geometria';

/** Tamaño de un hexágono (centro a esquina) en unidades del SVG. */
const TAM = 50;

interface HexDibujo {
  id: string;
  esquinas: string;
  color: string;
  centro: Punto;
  numero: number | null;
  rojo: boolean;
  pips: Punto[];
  nombre: string;
  /** Hay una opción seleccionada y este hexágono no la alimenta: se atenúa. */
  atenuado: boolean;
}

interface PuertoDibujo {
  marca: Punto;
  muelles: [Punto, Punto];
  color: string;
  /** Color del texto: claro sobre los fondos oscuros (madera, ladrillo). */
  tinta: string;
  texto: string;
  /** Recurso del puerto 2:1, escrito en la marca: el color solo no basta. */
  recurso: string | null;
  nombre: string;
}

interface PobladoDibujo {
  opcion: number;
  centro: Punto;
  color: string;
}

/**
 * Dibuja un tablero en SVG. Solo muestra: no pide datos ni guarda estado.
 *
 * Recibe el tablero de quien lo use (la demo hoy; la foto y la edición después), y
 * por eso sirve igual para cualquier origen.
 */
@Component({
  selector: 'app-tablero',
  templateUrl: './tablero.html',
})
export class TableroComponent {
  readonly tablero = input.required<Tablero>();
  /** Parejas recomendadas que se marcan encima; vacío si aún no se pidieron. */
  readonly opciones = input<Opcion[]>([]);
  readonly seleccionada = input(0);
  /** Avisa al padre qué opción tocó el usuario sobre el tablero. */
  readonly elegir = output<number>();

  protected readonly tam = TAM;

  /**
   * Hexágonos que tocan los dos poblados de la opción seleccionada. Salen del id de
   * cada vértice, que ya es la lista de sus tres hexágonos.
   */
  private readonly hexagonosDeLaSeleccionada = computed(() => {
    const opcion = this.opciones()[this.seleccionada()];
    return opcion ? new Set(opcion.vertices.flatMap((v) => v.split('|'))) : null;
  });

  protected readonly hexagonos = computed<HexDibujo[]>(() => {
    const resaltados = this.hexagonosDeLaSeleccionada();
    return this.tablero().hexagonos.map((h) => {
      const centro = centroHex(h.q, h.r, TAM);
      const numero = h.numero ?? null;
      return {
        id: h.id,
        esquinas: esquinasHex(centro, TAM * 0.97),
        color: COLOR_TERRENO[h.terreno],
        centro,
        numero,
        // El 6 y el 8 van en rojo en el juego físico: son los más probables.
        rojo: numero === 6 || numero === 8,
        pips: numero ? puntosPips(h.pips, centro, TAM) : [],
        nombre: numero ? `${h.terreno}, ${numero} (${h.pips} pips)` : h.terreno,
        atenuado: resaltados !== null && !resaltados.has(h.id),
      };
    });
  });

  protected readonly puertos = computed<PuertoDibujo[]>(() => {
    const enTablero = new Set(this.tablero().hexagonos.map((h) => h.id));
    return (this.tablero().puertos ?? []).map((p) => {
      const generico = p.tipo === '3:1';
      return {
        marca: posicionPuerto(p.vertices, enTablero, TAM),
        muelles: [centroVertice(p.vertices[0], TAM), centroVertice(p.vertices[1], TAM)],
        color: generico ? '#ffffff' : (COLOR_RECURSO[p.tipo as Recurso] ?? '#ffffff'),
        tinta: p.tipo === 'madera' || p.tipo === 'ladrillo' ? '#ffffff' : '#1f2937',
        texto: generico ? '3:1' : '2:1',
        recurso: generico ? null : p.tipo,
        nombre: generico ? 'Puerto 3:1' : `Puerto 2:1 de ${p.tipo}`,
      };
    });
  });

  /** Los dos poblados de la opción seleccionada, dibujados como casitas. */
  protected readonly poblados = computed<PobladoDibujo[]>(() => {
    const i = this.seleccionada();
    const opcion = this.opciones()[i];
    if (!opcion) return [];
    return opcion.vertices.map((v) => ({
      opcion: i,
      centro: centroVertice(v, TAM),
      color: COLOR_MEDALLA[i % COLOR_MEDALLA.length],
    }));
  });

  /**
   * Las otras opciones, como medallas pequeñas que se pueden tocar para
   * seleccionarlas. Se omite el vértice que coincida con un poblado seleccionado.
   */
  protected readonly otras = computed<PobladoDibujo[]>(() => {
    const i = this.seleccionada();
    const ocupados = new Set(this.opciones()[i]?.vertices ?? []);
    return this.opciones().flatMap((o, j) =>
      j === i
        ? []
        : o.vertices
            .filter((v) => !ocupados.has(v))
            .map((v) => ({
              opcion: j,
              centro: centroVertice(v, TAM),
              color: COLOR_MEDALLA[j % COLOR_MEDALLA.length],
            })),
    );
  });

  /** Encuadre del dibujo: los hexágonos más un anillo de mar para los puertos. */
  protected readonly marco = computed(() => {
    const centros = this.tablero().hexagonos.map((h) => centroHex(...leerCoordenada(h.id), TAM));
    const margen = TAM * 1.9;
    const xs = centros.map((c) => c.x);
    const ys = centros.map((c) => c.y);
    const x0 = Math.min(...xs) - margen;
    const y0 = Math.min(...ys) - margen;
    const ancho = Math.max(...xs) - Math.min(...xs) + 2 * margen;
    const alto = Math.max(...ys) - Math.min(...ys) + 2 * margen;
    return { x: x0, y: y0, ancho, alto };
  });

  protected readonly viewBox = computed(() => {
    const m = this.marco();
    return `${m.x} ${m.y} ${m.ancho} ${m.alto}`;
  });
}
