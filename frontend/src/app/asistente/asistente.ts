import { HttpErrorResponse } from '@angular/common/http';
import {
  Component,
  ElementRef,
  computed,
  inject,
  input,
  linkedSignal,
  output,
  signal,
  viewChild,
} from '@angular/core';

import { ColonoApi } from '../api/colono-api';
import type { Opcion, RespuestaRecomendar, Tablero } from '../api/tipos';
import {
  COLOR_MEDALLA,
  COLOR_RECURSO,
  ICONO_ESTRATEGIA,
  ICONO_RECURSO,
  MEDALLA,
  RECURSOS,
  type Recurso,
} from '../estilo-catan';

/** El mismo límite que valida el backend en `PeticionChat.pregunta`. */
export const LIMITE_PREGUNTA = 500;

/**
 * Un elemento de la conversación: un mensaje de texto, o el bloque con las
 * tarjetas de las opciones (que se pinta a partir de la respuesta del modelo).
 */
type Entrada =
  | { tipo: 'texto'; rol: 'usuario' | 'asistente'; texto: string; error?: boolean }
  | { tipo: 'opciones' };

/** Un trozo de texto, en negrita o no: el backend marca los nombres con **…**. */
export interface Trozo {
  texto: string;
  negrita: boolean;
}

/** Parte un texto con marcas **…** en trozos normales y en negrita. */
export function trocear(texto: string): Trozo[] {
  return texto
    .split('**')
    .map((t, i) => ({ texto: t, negrita: i % 2 === 1 }))
    .filter((t) => t.texto !== '');
}

interface Ficha {
  indice: number;
  opcion: Opcion;
  medalla: string;
  color: string;
  icono: string;
  puntos: string;
  desequilibrada: boolean;
  comparteCon: number[];
  produccion: { recurso: Recurso; icono: string; color: string; pips: number }[];
}

const BIENVENIDA =
  'Hola, soy tu asistente de Catan. Carga el **tablero de demostración** y pulsa ' +
  '**Recomendar**: te propongo dónde poner tus dos primeros poblados y te explico por qué.';

const PRESENTACION =
  'Estas son tus tres mejores colocaciones. 🥇 es la de mayor puntaje; 🥈 y 🥉 son la ' +
  'mejor opción de **otras estrategias**, para que tengas alternativas. Los puntos son ' +
  'una estimación: fíjate sobre todo en el orden. Toca una para ver el detalle.';

/**
 * Panel del asistente: pedir la recomendación, ver las opciones y conversar.
 *
 * Las opciones viven dentro de la conversación como tarjetas compactas, y una
 * franja fija arriba permite cambiar de opción sin buscarla en el chat. La
 * selección la guarda el padre (`App`), para que el tablero y el panel siempre
 * muestren la misma opción.
 */
@Component({
  selector: 'app-asistente',
  templateUrl: './asistente.html',
})
export class AsistenteComponent {
  private readonly api = inject(ColonoApi);

  readonly tablero = input<Tablero | null>(null);
  readonly respuesta = input<RespuestaRecomendar | null>(null);
  readonly seleccionada = input(0);
  readonly jugadores = input(4);
  readonly habilitado = input(false);
  readonly cargando = input(false);
  readonly error = input<string | null>(null);

  readonly recomendar = output<void>();
  readonly cambiarJugadores = output<number>();
  readonly seleccionar = output<number>();

  protected readonly limite = LIMITE_PREGUNTA;
  protected readonly trocear = trocear;
  protected readonly borrador = signal('');
  protected readonly pensando = signal(false);

  private readonly final = viewChild<ElementRef<HTMLElement>>('final');

  /**
   * La conversación. `linkedSignal` la reinicia sola cuando llega otra
   * recomendación o cambia el tablero: lo que se habló antes ya no aplica.
   */
  protected readonly entradas = linkedSignal<Entrada[]>(() => {
    this.tablero();
    return this.respuesta()
      ? [{ tipo: 'texto', rol: 'asistente', texto: PRESENTACION }, { tipo: 'opciones' }]
      : [{ tipo: 'texto', rol: 'asistente', texto: BIENVENIDA }];
  });

  /** Qué tarjeta tiene el detalle abierto; se cierra al llegar otra recomendación. */
  protected readonly abierta = linkedSignal<number | null>(() => {
    this.respuesta();
    return null;
  });

  protected readonly fichas = computed<Ficha[]>(() => {
    const opciones = this.respuesta()?.opciones ?? [];
    return opciones.map((opcion, indice) => ({
      indice,
      opcion,
      medalla: MEDALLA[indice] ?? `${indice + 1}.`,
      color: COLOR_MEDALLA[indice % COLOR_MEDALLA.length],
      icono: ICONO_ESTRATEGIA[opcion.estrategia] ?? '🎲',
      puntos: opcion.prediccion.toFixed(1),
      desequilibrada: opcion.estrategia === 'desequilibrada',
      comparteCon: opciones
        .map((otra, j) => ({ otra, j }))
        .filter(({ otra, j }) => j !== indice && otra.vertices.some((v) => opcion.vertices.includes(v)))
        .map(({ j }) => j + 1),
      produccion: RECURSOS.map((recurso) => ({
        recurso,
        icono: ICONO_RECURSO[recurso],
        color: COLOR_RECURSO[recurso],
        pips: opcion.variables[`pips_${recurso}`] ?? 0,
      })),
    }));
  });

  protected readonly sugerencias = computed(() => {
    const total = this.fichas().length;
    if (total === 0) return [];
    const n = this.seleccionada() + 1;
    const lista = [`¿Por qué la opción ${n}?`, '¿Qué construyo primero?', '¿Y si me quitan un vértice?'];
    if (total > 1) lista.push(`Compárala con la opción ${n === 1 ? 2 : 1}`);
    return lista;
  });

  /** Tocar una tarjeta la selecciona y abre o cierra su detalle. */
  protected tocarTarjeta(indice: number): void {
    this.seleccionar.emit(indice);
    this.abierta.update((actual) => (actual === indice ? null : indice));
  }

  protected enviar(texto: string): void {
    const pregunta = texto.trim().slice(0, LIMITE_PREGUNTA);
    if (!pregunta || this.pensando()) return;

    const respuesta = this.respuesta();
    const historial = this.entradas().flatMap((e) =>
      e.tipo === 'texto' && !e.error ? [{ rol: e.rol, texto: e.texto }] : [],
    );
    this.agregar({ tipo: 'texto', rol: 'usuario', texto: pregunta });
    this.borrador.set('');
    this.pensando.set(true);

    this.api
      .chat({
        pregunta,
        historial,
        tablero: this.tablero(),
        opciones: respuesta?.opciones ?? [],
        elegida: this.seleccionada(),
      })
      .subscribe({
        next: (r) => this.responder(respuesta, { tipo: 'texto', rol: 'asistente', texto: r.texto }),
        error: (e: HttpErrorResponse) =>
          this.responder(respuesta, {
            tipo: 'texto',
            rol: 'asistente',
            error: true,
            texto:
              e.status === 429
                ? 'Has hecho muchas preguntas seguidas. Espera un momento y vuelve a intentar.'
                : 'No pude responder ahora. Revisa la conexión e inténtalo de nuevo.',
          }),
      });
  }

  /** Si mientras tanto llegó otra recomendación, la respuesta ya no aplica. */
  private responder(respuesta: RespuestaRecomendar | null, entrada: Entrada): void {
    this.pensando.set(false);
    if (respuesta !== this.respuesta()) return;
    this.agregar(entrada);
  }

  private agregar(entrada: Entrada): void {
    this.entradas.update((e) => [...e, entrada]);
    // Tras pintar el mensaje nuevo, se lleva a la vista (en móvil, por encima del
    // campo de texto fijo gracias a su scroll-margin).
    setTimeout(() => this.final()?.nativeElement.scrollIntoView({ behavior: 'smooth', block: 'end' }));
  }
}
