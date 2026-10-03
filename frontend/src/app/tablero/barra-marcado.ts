import { Component, input, output } from '@angular/core';

import { PIEZAS_INICIALES, type ModoMarcado } from '../colocacion';

interface Boton {
  modo: Exclude<ModoMarcado, null>;
  etiqueta: string;
}

/**
 * Barra para marcar la colocación en curso: se elige un modo y luego se tocan
 * vértices del tablero. Es más rápido que un menú por vértice cuando varios rivales
 * colocan seguido, y en el celular no tapa el tablero.
 */
@Component({
  selector: 'app-barra-marcado',
  template: `
    <div class="flex flex-wrap items-center gap-2 rounded-xl bg-madera/80 p-2 text-sm text-crema">
      <span class="px-1 font-semibold">Marcar:</span>
      @for (b of botones; track b.modo) {
        @if (b.modo !== 'ciudad' || enPartida()) {
        <button
          type="button"
          class="rounded-lg border border-amber-100/40 px-3 py-1.5"
          [class.bg-crema]="modo() === b.modo"
          [class.text-madera]="modo() === b.modo"
          [attr.aria-pressed]="modo() === b.modo"
          (click)="cambiarModo.emit(modo() === b.modo ? null : b.modo)"
        >
          {{ b.etiqueta }}
        </button>
        }
      }
      <button
        type="button"
        class="rounded-lg px-3 py-1.5 underline-offset-2 hover:underline disabled:opacity-50"
        [disabled]="!propios() && !ciudades() && !rivales()"
        (click)="limpiar.emit()"
      >
        Limpiar
      </button>
      <span class="ml-auto px-1 text-amber-100/90">
        @if (enPartida()) {
          Tus poblados: {{ propios() }} · Ciudades: {{ ciudades() }} · Rivales: {{ rivales() }}
        } @else {
          Tus poblados: {{ propios() }}/{{ iniciales }} · Rivales: {{ rivales() }}
        }
      </span>
    </div>
  `,
})
export class BarraMarcadoComponent {
  readonly modo = input<ModoMarcado>(null);
  readonly propios = input(0);
  readonly rivales = input(0);
  readonly ciudades = input(0);
  /** Terminó la colocación inicial: aparece el modo Ciudad y no hay tope de 2. */
  readonly enPartida = input(false);

  readonly cambiarModo = output<ModoMarcado>();
  readonly limpiar = output<void>();

  protected readonly iniciales = PIEZAS_INICIALES;
  protected readonly botones: Boton[] = [
    { modo: 'propio', etiqueta: '🏠 Mi poblado' },
    { modo: 'ciudad', etiqueta: '🏰 Ciudad' },
    { modo: 'rival', etiqueta: '⛔ Rival' },
    { modo: 'borrar', etiqueta: '✖ Borrar' },
  ];
}
