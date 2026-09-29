import { Component, computed, input, output } from '@angular/core';

import type { Destino, Opcion, Tablero } from '../api/tipos';
import type { Marca, Marcas, ModoMarcado } from '../colocacion';
import type { Arista } from '../revision/costa';
import { COLOR_MEDALLA, COLOR_RECURSO, COLOR_TERRENO, type Recurso } from '../estilo-catan';
import {
  Punto,
  centroHex,
  centroVertice,
  rutaEnPuntos,
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
  /** Revisión: la visión no está segura de su terreno. */
  dudoso: boolean;
  /** Revisión: la visión leyó el número con poco margen. */
  numeroDudoso: boolean;
  seleccionado: boolean;
  desierto: boolean;
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

interface MarcaDibujo {
  id: string;
  centro: Punto;
  tipo: Marca;
}

/** Un vértice que se puede tocar en modo de marcado. */
interface PuntoDibujo {
  id: string;
  centro: Punto;
  estado: 'libre' | 'bloqueado' | 'marcado';
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

  /** Vértices marcados por el usuario: su poblado y los de los rivales. */
  readonly marcas = input<Marcas>({});
  /** Con un modo activo, los vértices se pueden tocar para marcarlos. */
  readonly modo = input<ModoMarcado>(null);
  /** Marcados y sus vecinos: la regla de distancia los deja fuera. */
  readonly bloqueados = input<ReadonlySet<string>>(new Set());
  /** El usuario tocó un vértice en modo de marcado; el padre decide qué hacer. */
  readonly tocarVertice = output<string>();

  // --- Revisión del tablero --------------------------------------------------------
  /** En revisión se tocan hexágonos y puertos para corregirlos. */
  readonly revision = input(false);
  readonly dudosos = input<ReadonlySet<string>>(new Set());
  readonly numerosDudosos = input<ReadonlySet<string>>(new Set());
  readonly hexSeleccionado = input<string | null>(null);
  readonly puertoSeleccionado = input<number | null>(null);
  /** Aristas de costa a las que se puede mover el puerto seleccionado. */
  readonly destinos = input<Arista[]>([]);
  /** Colocación completa: dónde crecer (A, B, C) y la ruta de caminos hasta allí. */
  readonly crecimiento = input<Destino[]>([]);
  readonly tocarHexagono = output<string>();
  readonly tocarPuerto = output<number>();
  readonly tocarArista = output<Arista>();

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
        dudoso: this.dudosos().has(h.id),
        numeroDudoso: this.numerosDudosos().has(h.id),
        seleccionado: this.hexSeleccionado() === h.id,
        desierto: h.terreno === 'desierto',
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
    const marcas = this.marcas();
    return opcion.vertices.filter((v) => !marcas[v]).map((v) => ({
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
    const ocupados = new Set([...(this.opciones()[i]?.vertices ?? []), ...Object.keys(this.marcas())]);
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

  protected readonly segmentosDestino = computed(() =>
    this.destinos().map((arista) => ({
      arista,
      a: centroVertice(arista[0], TAM),
      b: centroVertice(arista[1], TAM),
    })),
  );

  protected readonly caminosDeCrecimiento = computed(() =>
    this.crecimiento().map((d) => ({
      letra: d.letra,
      ruta: rutaEnPuntos(d.ruta, TAM),
      centro: centroVertice(d.vertice, TAM),
      descripcion: d.descripcion,
    })),
  );

  protected readonly marcados = computed<MarcaDibujo[]>(() =>
    Object.entries(this.marcas()).map(([id, tipo]) => ({ id, tipo, centro: centroVertice(id, TAM) })),
  );

  /** Los 54 vértices, solo cuando se está marcando. */
  protected readonly puntos = computed<PuntoDibujo[]>(() => {
    if (this.modo() === null) return [];
    const marcas = this.marcas();
    const bloqueados = this.bloqueados();
    return this.tablero().vertices.map((v) => ({
      id: v.id,
      centro: centroVertice(v.id, TAM),
      estado: marcas[v.id] ? 'marcado' : bloqueados.has(v.id) ? 'bloqueado' : 'libre',
    }));
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
