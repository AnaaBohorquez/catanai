import { HttpErrorResponse } from '@angular/common/http';
import {
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  input,
  linkedSignal,
  output,
  signal,
  untracked,
  viewChild,
} from '@angular/core';

import { ColonoApi } from '../api/colono-api';
import type {
  EstadoColocacion,
  Opcion,
  RespuestaChat,
  RespuestaRecomendar,
  Salud,
  Tablero,
} from '../api/tipos';
import {
  COLOR_MEDALLA,
  COLOR_RECURSO,
  ICONO_ESTRATEGIA,
  ICONO_RECURSO,
  MEDALLA,
  RECURSOS,
  type Recurso,
} from '../estilo-catan';

/** Aviso de que las opciones cambiaron por las marcas del tablero. */
export interface Actualizacion {
  n: number;
  texto: string;
}

/** El mismo límite que valida el backend en `PeticionChat.pregunta`. */
export const LIMITE_PREGUNTA = 500;

type Fuente = RespuestaChat['fuentes'][number];

/** Cómo se muestra cada fuente bajo una respuesta, en lenguaje de jugador. */
export const ETIQUETA_FUENTE: Record<Fuente, string> = {
  modelo: '📊 Según el modelo',
  reglas: '📖 Regla del juego',
  general: '💡 Consejo general',
};

/**
 * Un elemento de la conversación: un mensaje de texto, o un bloque de tarjetas con
 * las opciones que había en ese momento. Cada bloque guarda su propia copia, porque
 * el asistente puede pedir opciones nuevas y las anteriores deben seguir legibles.
 */
type Entrada =
  | {
      tipo: 'texto';
      rol: 'usuario' | 'asistente';
      texto: string;
      error?: boolean;
      fuentes?: Fuente[];
      /** Respondida sin IA, con plantillas: entiende menos preguntas. */
      basico?: boolean;
    }
  | { tipo: 'opciones'; opciones: Opcion[] };

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
  /** Segunda colocación: la descripción del poblado nuevo (el otro ya es tuyo). */
  segundo: string | null;
}

/** Lo que muestran la franja y las tarjetas de un conjunto de opciones. */
export function fichasDe(opciones: Opcion[], mio: string | null = null): Ficha[] {
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
    segundo: mio && opcion.vertices.includes(mio)
      ? opcion.descripciones[opcion.vertices[0] === mio ? 1 : 0]
      : null,
  }));
}

const BIENVENIDA =
  'Hola, soy tu asistente de Catan. Carga el **tablero de demostración** y pulsa ' +
  '**Recomendar**: te propongo dónde poner tus dos primeros poblados y te explico por qué.';

const PRESENTACION_SEGUNDA =
  'Tu primer poblado ya está en el tablero. Estas son las mejores opciones para tu ' +
  '**segundo poblado**: 🥇 es la de mayor puntaje; 🥈 y 🥉 son alternativas, de otra ' +
  'estrategia cuando la hay. Los puntos son una estimación: fíjate sobre todo en el orden.';

const PRESENTACION =
  'Estas son tus tres mejores colocaciones. 🥇 es la de mayor puntaje; 🥈 y 🥉 son ' +
  'alternativas, de **otra estrategia** cuando la hay. Los puntos son una estimación: ' +
  'fíjate sobre todo en el orden. Toca una para ver el detalle.';

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
  /**
   * Número de conversación: `App` lo sube al cargar un tablero, recomendar o
   * cambiar de jugadores. Solo entonces se reinicia el chat; si el asistente pide
   * opciones nuevas, la conversación sigue.
   */
  readonly conversacion = input(0);
  readonly seleccionada = input(0);
  readonly jugadores = input(4);
  /** Estado de la colocación: viaja con cada pregunta para que el chat lo vea. */
  readonly ocupados = input<string[]>([]);
  readonly mio = input<string | null>(null);
  /** Los dos poblados propios ya están puestos. */
  readonly completo = input(false);
  readonly actualizacion = input<Actualizacion | null>(null);
  readonly habilitado = input(false);
  readonly cargando = input(false);
  readonly error = input<string | null>(null);
  /** Por qué el chat está sin IA según `/health`, o null si la usa. */
  readonly motivoBasico = input<Salud['chat_motivo']>(null);

  readonly recomendar = output<void>();
  readonly cambiarJugadores = output<number>();
  readonly seleccionar = output<number>();
  /** El asistente pidió otra recomendación: el padre reemplaza las opciones. */
  readonly opcionesNuevas = output<Opcion[]>();
  /** El asistente recalculó con una hipótesis: el padre marca el tablero. */
  readonly estadoNuevo = output<EstadoColocacion>();

  protected readonly limite = LIMITE_PREGUNTA;
  protected readonly trocear = trocear;
  protected readonly fichasDe = fichasDe;
  protected readonly etiquetaFuente = ETIQUETA_FUENTE;
  protected readonly borrador = signal('');
  protected readonly pensando = signal(false);

  private readonly final = viewChild<ElementRef<HTMLElement>>('final');

  /**
   * Si la última respuesta llegó sin IA. Manda sobre `/health`, que se consulta
   * solo al abrir la página: la clave puede fallar (o volver) después.
   */
  private readonly ultimaBasica = signal<boolean | null>(null);
  protected readonly modoBasico = computed(() => this.ultimaBasica() ?? !!this.motivoBasico());

  /**
   * La conversación. `linkedSignal` la reinicia sola cuando cambia el número de
   * conversación. La respuesta se lee con `untracked` para que recibir opciones
   * nuevas desde el chat no borre lo que se habló.
   */
  protected readonly entradas = linkedSignal<Entrada[]>(() => {
    this.conversacion();
    const respuesta = untracked(this.respuesta);
    const presentacion = respuesta?.momento === 'segunda' ? PRESENTACION_SEGUNDA : PRESENTACION;
    return respuesta
      ? [
          { tipo: 'texto', rol: 'asistente', texto: presentacion },
          { tipo: 'opciones', opciones: respuesta.opciones },
        ]
      : [{ tipo: 'texto', rol: 'asistente', texto: BIENVENIDA }];
  });

  /** Qué tarjeta tiene el detalle abierto; se cierra al cambiar las opciones. */
  protected readonly abierta = linkedSignal<number | null>(() => {
    this.respuesta();
    return null;
  });

  /** Las opciones vigentes: las de la franja y el tablero. */
  protected readonly fichas = computed<Ficha[]>(() =>
    fichasDe(this.respuesta()?.opciones ?? [], this.mio()),
  );

  constructor() {
    // Las marcas cambiaron y App recalculó: se avisa en el chat y se agrega el
    // bloque de tarjetas nuevo, sin borrar la conversación.
    effect(() => {
      const aviso = this.actualizacion();
      if (!aviso) return;
      untracked(() => {
        this.agregar({ tipo: 'texto', rol: 'asistente', texto: aviso.texto });
        const opciones = this.respuesta()?.opciones;
        if (opciones?.length) this.agregar({ tipo: 'opciones', opciones });
      });
    });
  }

  protected readonly sugerencias = computed(() => {
    const total = this.fichas().length;
    if (total === 0) return [];
    const n = this.seleccionada() + 1;
    const lista = [`¿Por qué la opción ${n}?`, '¿Qué estrategia sigo?', '¿Y si me quitan un vértice?'];
    if (total > 1) lista.push(`Compárala con la opción ${n === 1 ? 2 : 1}`);
    return lista;
  });

  /** Un bloque de tarjetas que ya no es el vigente se muestra atenuado y sin tocar. */
  protected esVigente(opciones: Opcion[]): boolean {
    return opciones === this.respuesta()?.opciones;
  }

  /** Tocar una tarjeta la selecciona y abre o cierra su detalle. */
  protected tocarTarjeta(indice: number): void {
    this.seleccionar.emit(indice);
    this.abierta.update((actual) => (actual === indice ? null : indice));
  }

  /** El botón de la tarjeta pregunta por la estrategia de esa opción. */
  protected preguntarEstrategia(f: Ficha): void {
    this.seleccionar.emit(f.indice);
    this.enviar(
      `¿Cómo juego la estrategia ${f.opcion.explicacion.titulo} de la opción ${f.indice + 1}?`,
      f.indice,
    );
  }

  /**
   * `elegida` se pasa aparte cuando la pregunta sale de una tarjeta: la selección
   * que acaba de emitirse aún no ha vuelto como `input` del padre.
   */
  protected enviar(texto: string, elegida = this.seleccionada()): void {
    const pregunta = texto.trim().slice(0, LIMITE_PREGUNTA);
    if (!pregunta || this.pensando()) return;

    const conversacion = this.conversacion();
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
        opciones: this.respuesta()?.opciones ?? [],
        elegida,
        ocupados: this.ocupados(),
        mio: this.mio(),
        jugadores: this.jugadores(),
      })
      .subscribe({
        next: (r) => {
          if (!this.sigueVigente(conversacion)) return;
          const basico = r.fuente === 'plantillas';
          this.ultimaBasica.set(basico);
          this.agregar({ tipo: 'texto', rol: 'asistente', texto: r.texto, fuentes: r.fuentes, basico });
          // Primero las marcas y luego las opciones: así App sabe que ya coinciden
          // y no vuelve a recalcular.
          if (r.estado_nuevo) this.estadoNuevo.emit(r.estado_nuevo);
          if (r.opciones_nuevas?.length) {
            this.opcionesNuevas.emit(r.opciones_nuevas);
            this.agregar({ tipo: 'opciones', opciones: r.opciones_nuevas });
          }
        },
        error: (e: HttpErrorResponse) => {
          if (!this.sigueVigente(conversacion)) return;
          this.agregar({
            tipo: 'texto',
            rol: 'asistente',
            error: true,
            texto:
              e.status === 429
                ? 'Has hecho muchas preguntas seguidas. Espera unos minutos y vuelve a intentar.'
                : 'No pude responder ahora. Revisa la conexión e inténtalo de nuevo.',
          });
        },
      });
  }

  /** Si mientras tanto se cargó otro tablero o se recomendó de nuevo, se descarta. */
  private sigueVigente(conversacion: number): boolean {
    this.pensando.set(false);
    return conversacion === this.conversacion();
  }

  private agregar(entrada: Entrada): void {
    this.entradas.update((e) => [...e, entrada]);
    // Tras pintar el mensaje nuevo, se lleva a la vista (en móvil, por encima del
    // campo de texto fijo gracias a su scroll-margin).
    setTimeout(() => this.final()?.nativeElement.scrollIntoView({ behavior: 'smooth', block: 'end' }));
  }
}
