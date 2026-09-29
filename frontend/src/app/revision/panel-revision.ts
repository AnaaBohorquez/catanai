import { Component, computed, input, output } from '@angular/core';

import type { Hexagono, Tablero, Terreno } from '../api/tipos';
import { COLOR_RECURSO, COLOR_TERRENO, ICONO_RECURSO, RECURSOS } from '../estilo-catan';
import { NOMBRE_TERRENO, NUMEROS, conteoFichas, conteoTerrenos, sinNumero } from './reparto';

const ICONO_TERRENO: Record<Terreno, string> = {
  bosque: '🌲',
  pastos: '🐑',
  campos: '🌾',
  colinas: '🧱',
  montanas: '⛰️',
  desierto: '🏜️',
};

/**
 * Panel para revisar el tablero antes de recomendar: corregir el terreno y el número
 * de cada hexágono, el tipo de cada puerto, y confirmar. Solo muestra y avisa; el
 * tablero lo cambia `App`.
 */
@Component({
  selector: 'app-panel-revision',
  templateUrl: './panel-revision.html',
})
export class PanelRevisionComponent {
  readonly tablero = input.required<Tablero>();
  readonly hexagono = input<Hexagono | null>(null);
  readonly puerto = input<number | null>(null);
  /** Lo que dijo la visión ("revisa los marcados en amarillo…"), si vino de una foto. */
  readonly mensaje = input<string | null>(null);
  readonly dudosos = input(0);
  readonly numerosDudosos = input(0);
  /** Avisos del backend al confirmar; null mientras no se ha intentado. */
  readonly avisos = input<string[] | null>(null);
  readonly confirmando = input(false);
  /** Qué se reacomodó solo tras la última corrección. */
  readonly ajuste = input<string | null>(null);
  /** Opciones más probables del hexágono dudoso seleccionado, para elegir de un toque. */
  readonly sugerenciasNumero = input<number[]>([]);
  readonly sugerenciasTerreno = input<Terreno[]>([]);

  readonly cambiarTerreno = output<Terreno>();
  readonly cambiarNumero = output<number | null>();
  readonly siguiente = output<void>();
  readonly cambiarTipoPuerto = output<string>();
  readonly girar = output<void>();
  readonly confirmar = output<void>();
  readonly continuar = output<void>();
  readonly volver = output<void>();
  readonly descartar = output<void>();
  readonly aceptarTodo = output<void>();

  protected readonly terrenos = Object.keys(NOMBRE_TERRENO) as Terreno[];
  protected readonly nombreTerreno = NOMBRE_TERRENO;
  protected readonly iconoTerreno = ICONO_TERRENO;
  protected readonly colorTerreno = COLOR_TERRENO;
  protected readonly numeros = NUMEROS;
  protected readonly tiposPuerto = [
    { tipo: '3:1', etiqueta: '3:1', color: '#ffffff' },
    ...RECURSOS.map((r) => ({ tipo: r, etiqueta: `${ICONO_RECURSO[r]} ${r}`, color: COLOR_RECURSO[r] })),
  ];

  protected readonly terrenosContados = computed(() => conteoTerrenos(this.tablero().hexagonos));
  protected readonly fichasFaltantes = computed(() =>
    conteoFichas(this.tablero().hexagonos).filter((c) => c.hay !== c.esperado),
  );
  protected readonly pendientes = computed(() => sinNumero(this.tablero().hexagonos).length);
  protected readonly tipoPuerto = computed(() => {
    const i = this.puerto();
    return i === null ? null : (this.tablero().puertos[i]?.tipo ?? null);
  });
}
