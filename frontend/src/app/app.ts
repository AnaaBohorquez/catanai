import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, effect, inject, signal, untracked } from '@angular/core';
import { timeout } from 'rxjs';

import { ColonoApi } from './api/colono-api';
import type {
  EstadoColocacion,
  Hexagono,
  Opcion,
  RespuestaRecomendar,
  Tablero,
  Terreno,
} from './api/tipos';
import { AsistenteComponent, type Actualizacion } from './asistente/asistente';
import {
  MAX_PROPIOS,
  type Marcas,
  type ModoMarcado,
  firma,
  propios,
  rivales,
} from './colocacion';
import { reducirFoto } from './foto/reducir';
import { type Arista, destinosPosibles, girarPuertos } from './revision/costa';
import { PanelRevisionComponent } from './revision/panel-revision';
import { RECURSO_DE_TERRENO, pipsDe, sinNumero } from './revision/reparto';
import { BarraMarcadoComponent } from './tablero/barra-marcado';
import { bloqueados } from './tablero/geometria';
import { TableroComponent } from './tablero/tablero';

/** En qué punto está la conexión con el backend. */
type EstadoServidor = 'conectando' | 'despertando' | 'listo' | 'degradado' | 'sin-conexion';

/**
 * El plan gratuito de Render duerme el servidor tras 15 min sin uso y tarda cerca
 * de un minuto en despertar. Si a los 3 s no hay respuesta, se avisa de eso en vez
 * de dejar al usuario frente a una pantalla que parece rota.
 */
const AVISO_DESPERTAR_MS = 3_000;
const LIMITE_ESPERA_MS = 90_000;

/** Espera tras el último toque antes de recalcular: agrupa varios toques seguidos. */
const ESPERA_RECALCULO_MS = 400;
const DURACION_AVISO_MS = 3_500;

/** Por debajo de esta confianza, la visión pide revisar el terreno. */
const CONFIANZA_DUDOSA = 0.55;
/** Por debajo de esta confianza, el número se leyó con poco margen: se revisa. */
const CONFIANZA_NUMERO = 0.5;

@Component({
  imports: [TableroComponent, AsistenteComponent, BarraMarcadoComponent, PanelRevisionComponent],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App implements OnInit {
  private readonly api = inject(ColonoApi);

  protected readonly servidor = signal<EstadoServidor>('conectando');
  protected readonly conectado = computed(() => {
    const estado = this.servidor();
    return estado === 'listo' || estado === 'degradado';
  });

  /** El tablero en pantalla, venga de la demo o (más adelante) de una foto. */
  protected readonly tablero = signal<Tablero | null>(null);
  protected readonly cargando = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly jugadores = signal(4);
  protected readonly respuesta = signal<RespuestaRecomendar | null>(null);
  /**
   * La opción que se está mirando. Es el único estado de selección: lo cambian el
   * tablero, la franja y las tarjetas del chat, y todos lo leen de aquí.
   */
  protected readonly seleccionada = signal(0);
  /** En móvil el tablero se puede plegar para dejarle la pantalla al chat. */
  protected readonly tableroVisible = signal(true);
  protected readonly recomendando = signal(false);
  protected readonly errorRecomendar = signal<string | null>(null);
  /**
   * Sube cada vez que empieza una conversación nueva: otro tablero u otra
   * recomendación pedida con el botón. Los recálculos por marcas y las opciones que
   * pide el asistente no la cambian, para no borrar lo que se estaba hablando.
   */
  protected readonly conversacion = signal(0);
  /** Avisa al asistente de que las opciones cambiaron por las marcas del tablero. */
  protected readonly actualizacion = signal<Actualizacion | null>(null);

  // --- Colocación en curso ------------------------------------------------------

  /** Lo que el usuario marcó. Es la única verdad de lo ocupado. */
  protected readonly marcas = signal<Marcas>({});
  protected readonly modo = signal<ModoMarcado>(null);
  protected readonly aviso = signal<string | null>(null);

  protected readonly propios = computed(() => propios(this.marcas()));
  protected readonly ocupados = computed(() => rivales(this.marcas()));
  /** Con un solo poblado propio, es tu primer poblado: se recomienda el segundo. */
  protected readonly mio = computed(() => (this.propios().length === 1 ? this.propios()[0] : null));
  /** Con los dos poblados propios puestos, ya no hay nada que recomendar. */
  protected readonly completo = computed(() => this.propios().length >= MAX_PROPIOS);
  protected readonly bloqueados = computed<ReadonlySet<string>>(() =>
    bloqueados(Object.keys(this.marcas()), (this.tablero()?.vertices ?? []).map((v) => v.id)),
  );

  // --- Foto y revisión del tablero ----------------------------------------------

  protected readonly leyendoFoto = signal(false);
  /** Revisando: se corrigen terrenos, números y puertos antes de recomendar. */
  protected readonly revisando = signal(false);
  protected readonly dudosos = signal<ReadonlySet<string>>(new Set());
  /** Hexágonos cuyo número leyó la visión con poco margen: se revisan a mano. */
  protected readonly numerosDudosos = signal<ReadonlySet<string>>(new Set());
  protected readonly hexSeleccionado = signal<string | null>(null);
  protected readonly puertoSeleccionado = signal<number | null>(null);
  protected readonly mensajeRevision = signal<string | null>(null);
  protected readonly avisosRevision = signal<string[] | null>(null);
  protected readonly confirmando = signal(false);

  protected readonly hexagono = computed<Hexagono | null>(
    () => this.tablero()?.hexagonos.find((h) => h.id === this.hexSeleccionado()) ?? null,
  );
  protected readonly destinos = computed<Arista[]>(() => {
    const t = this.tablero();
    const i = this.puertoSeleccionado();
    return t && i !== null ? destinosPosibles(t, i) : [];
  });

  /** El tablero de antes de revisar, para "Descartar cambios". */
  private respaldo: Tablero | null = null;
  /** El tablero ya validado por el backend, a la espera de "Continuar de todos modos". */
  private validado: Tablero | null = null;

  /** Tras el primer "Recomendar" de un tablero, las marcas recalculan solas. */
  private recomendacionActiva = false;
  /** Marcas y jugadores con los que se calcularon las opciones en pantalla. */
  private firmaRespuesta: string | null = null;
  /** Descarta respuestas viejas si el usuario tocó más vértices mientras tanto. */
  private pedido = 0;
  private temporizadorAviso: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    // Recalcular cuando cambian las marcas o los jugadores, con una espera corta
    // para no llamar al backend en cada toque de una ráfaga.
    effect((alLimpiar) => {
      const marcas = this.marcas();
      const jugadores = this.jugadores();
      if (!this.recomendacionActiva || !untracked(this.tablero)) return;
      if (firma(marcas, jugadores) === this.firmaRespuesta) return;
      const espera = setTimeout(() => this.recalcular('marcas'), ESPERA_RECALCULO_MS);
      alLimpiar(() => clearTimeout(espera));
    });
  }

  ngOnInit(): void {
    this.comprobarServidor();
  }

  protected comprobarServidor(): void {
    this.servidor.set('conectando');
    const aviso = setTimeout(() => this.servidor.set('despertando'), AVISO_DESPERTAR_MS);
    this.api
      .salud()
      .pipe(timeout(LIMITE_ESPERA_MS))
      .subscribe({
        next: (salud) => {
          clearTimeout(aviso);
          this.servidor.set(salud.modelo_cargado ? 'listo' : 'degradado');
        },
        error: () => {
          clearTimeout(aviso);
          this.servidor.set('sin-conexion');
        },
      });
  }

  protected pedirTableroDemo(): void {
    this.cargando.set(true);
    this.error.set(null);
    this.api.tableroAleatorio().subscribe({
      next: (tablero) => {
        this.tablero.set(tablero);
        // Las opciones y las marcas eran de otro tablero: ya no valen.
        this.respuesta.set(null);
        this.marcas.set({});
        this.modo.set(null);
        this.recomendacionActiva = false;
        this.firmaRespuesta = null;
        this.errorRecomendar.set(null);
        this.conversacion.update((n) => n + 1);
        this.cargando.set(false);
      },
      error: (e: HttpErrorResponse) => {
        this.error.set(mensajeDeError(e));
        this.cargando.set(false);
      },
    });
  }

  /** Tomar o subir una foto: se reduce en el navegador y se lee en el backend. */
  protected async subirFoto(evento: Event): Promise<void> {
    const entrada = evento.target as HTMLInputElement;
    const archivo = entrada.files?.[0];
    entrada.value = ''; // permite volver a elegir la misma foto
    if (!archivo) return;
    this.leyendoFoto.set(true);
    this.error.set(null);
    let foto: Blob;
    try {
      foto = await reducirFoto(archivo);
    } catch {
      this.error.set('No se pudo abrir esa imagen. Prueba con una foto JPG o PNG.');
      this.leyendoFoto.set(false);
      return;
    }
    this.api.leerFoto(foto).subscribe({
      next: (lectura) => {
        this.respaldo = this.tablero();
        const dudosos = lectura.detecciones
          .filter((d) => d.confianza_terreno < CONFIANZA_DUDOSA)
          .map((d) => d.id);
        const numerosDudosos = lectura.detecciones
          .filter((d) => d.numero && d.confianza_numero < CONFIANZA_NUMERO)
          .map((d) => d.id);
        this.entrarEnRevision(lectura.tablero, new Set(dudosos), lectura.mensaje, new Set(numerosDudosos));
        this.leyendoFoto.set(false);
      },
      error: (e: HttpErrorResponse) => {
        // Se conserva el tablero anterior: una foto fallida no debe borrar nada.
        this.error.set(mensajeDeError(e));
        this.leyendoFoto.set(false);
      },
    });
  }

  /** Editar a mano cualquier tablero, por ejemplo el de demostración. */
  protected editarTablero(): void {
    const tablero = this.tablero();
    if (!tablero) return;
    this.respaldo = tablero;
    this.entrarEnRevision(tablero, new Set(), null, new Set());
  }

  private entrarEnRevision(
    tablero: Tablero,
    dudosos: ReadonlySet<string>,
    mensaje: string | null,
    numerosDudosos: ReadonlySet<string>,
  ) {
    this.tablero.set(tablero);
    // Un tablero en revisión todavía no sirve para recomendar: marcas y opciones fuera.
    this.respuesta.set(null);
    this.marcas.set({});
    this.modo.set(null);
    this.recomendacionActiva = false;
    this.firmaRespuesta = null;
    this.errorRecomendar.set(null);
    this.conversacion.update((n) => n + 1);

    this.revisando.set(true);
    this.dudosos.set(dudosos);
    this.numerosDudosos.set(numerosDudosos);
    this.mensajeRevision.set(mensaje);
    this.avisosRevision.set(null);
    this.puertoSeleccionado.set(null);
    // Se empieza por lo que más urge: un terreno dudoso o, si no, un hexágono sin número.
    const primero = tablero.hexagonos.find((h) => dudosos.has(h.id)) ?? sinNumero(tablero.hexagonos)[0];
    this.hexSeleccionado.set(primero?.id ?? null);
  }

  protected tocarHexagono(id: string): void {
    this.hexSeleccionado.set(id);
    this.puertoSeleccionado.set(null);
  }

  protected cambiarTerreno(terreno: Terreno): void {
    this.editarHexagono((h) => ({
      ...h,
      terreno,
      recurso: RECURSO_DE_TERRENO[terreno],
      // El desierto no lleva ficha.
      numero: terreno === 'desierto' ? null : h.numero,
      pips: terreno === 'desierto' ? 0 : h.pips,
    }));
    // Corregido a mano: deja de ser dudoso.
    const id = this.hexSeleccionado();
    if (id) this.dudosos.update((d) => new Set([...d].filter((x) => x !== id)));
  }

  protected cambiarNumero(numero: number | null): void {
    const teniaNumero = !!this.hexagono()?.numero;
    const id = this.hexSeleccionado();
    const eraDudoso = !!id && this.numerosDudosos().has(id);
    this.editarHexagono((h) => ({ ...h, numero, pips: pipsDe(numero) }));
    // Revisado a mano (aunque se confirme el mismo número): deja de ser dudoso.
    if (id) this.numerosDudosos.update((d) => new Set([...d].filter((x) => x !== id)));
    // Al poner un número nuevo o revisar uno dudoso se pasa al siguiente pendiente:
    // la revisión se hace tocando solo números, sin volver al tablero.
    if (numero && (!teniaNumero || eraDudoso)) this.siguienteSinNumero();
  }

  protected siguienteSinNumero(): void {
    const t = this.tablero();
    if (!t) return;
    const dudosos = this.numerosDudosos();
    const pendientes = [
      ...sinNumero(t.hexagonos),
      ...t.hexagonos.filter((h) => dudosos.has(h.id)),
    ];
    const actual = t.hexagonos.findIndex((h) => h.id === this.hexSeleccionado());
    const despues = pendientes.find((h) => t.hexagonos.indexOf(h) > actual) ?? pendientes[0];
    if (despues) this.hexSeleccionado.set(despues.id);
  }

  private editarHexagono(cambio: (h: Hexagono) => Hexagono): void {
    const id = this.hexSeleccionado();
    this.tablero.update((t) =>
      t ? { ...t, hexagonos: t.hexagonos.map((h) => (h.id === id ? cambio(h) : h)) } : t,
    );
    this.avisosRevision.set(null);
  }

  protected tocarPuerto(indice: number): void {
    this.puertoSeleccionado.set(this.puertoSeleccionado() === indice ? null : indice);
    this.hexSeleccionado.set(null);
  }

  protected cambiarTipoPuerto(tipo: string): void {
    const i = this.puertoSeleccionado();
    this.tablero.update((t) =>
      t ? { ...t, puertos: t.puertos.map((p, j) => (j === i ? { ...p, tipo } : p)) } : t,
    );
  }

  protected girarPuertos(): void {
    this.tablero.update((t) => (t ? { ...t, puertos: girarPuertos(t) } : t));
  }

  protected moverPuerto(arista: Arista): void {
    const i = this.puertoSeleccionado();
    this.tablero.update((t) =>
      t
        ? { ...t, puertos: t.puertos.map((p, j) => (j === i ? { ...p, vertices: [...arista] } : p)) }
        : t,
    );
  }

  /** El backend reconstruye el tablero (pips, vértices, puertos) y dice qué no cuadra. */
  protected confirmarTablero(): void {
    const t = this.tablero();
    if (!t) return;
    this.confirmando.set(true);
    this.api.validar(t).subscribe({
      next: ({ tablero, avisos }) => {
        this.confirmando.set(false);
        if (avisos?.length) {
          this.validado = tablero;
          this.avisosRevision.set(avisos);
        } else {
          this.salirDeRevision(tablero);
        }
      },
      error: (e: HttpErrorResponse) => {
        this.confirmando.set(false);
        this.avisosRevision.set([mensajeDeError(e)]);
      },
    });
  }

  protected continuarConAvisos(): void {
    if (this.validado) this.salirDeRevision(this.validado);
  }

  protected descartarRevision(): void {
    this.salirDeRevision(this.respaldo);
  }

  private salirDeRevision(tablero: Tablero | null): void {
    this.tablero.set(tablero);
    this.revisando.set(false);
    this.hexSeleccionado.set(null);
    this.puertoSeleccionado.set(null);
    this.avisosRevision.set(null);
    this.mensajeRevision.set(null);
    this.dudosos.set(new Set());
    this.numerosDudosos.set(new Set());
    this.validado = null;
    this.respaldo = null;
  }

  protected cambiarJugadores(n: number): void {
    // Si ya hay recomendación, el efecto recalcula con el nuevo número.
    this.jugadores.set(n);
  }

  /**
   * Un toque sobre un vértice en modo de marcado. Aquí se aplican las reglas: la
   * distancia entre poblados y el máximo de dos poblados propios.
   */
  protected tocarVertice(id: string): void {
    const modo = this.modo();
    const actual = this.marcas()[id];
    if (modo === null) return;

    if (modo === 'borrar' || actual === modo) {
      if (actual) this.marcas.update(({ [id]: _, ...resto }) => resto);
      return;
    }
    if (!actual && this.bloqueados().has(id)) {
      this.avisar('Ese vértice está junto a otro poblado (regla de distancia).');
      return;
    }
    if (modo === 'propio' && this.propios().length >= MAX_PROPIOS) {
      this.avisar('Ya marcaste tus dos poblados. Borra uno para cambiarlo.');
      return;
    }
    this.marcas.update((m) => ({ ...m, [id]: modo }));
  }

  protected limpiarMarcas(): void {
    this.marcas.set({});
  }

  protected pedirRecomendacion(): void {
    this.recomendacionActiva = true;
    this.recalcular('boton');
  }

  /**
   * El asistente recalculó con una hipótesis ("¿y si un rival toma…?"): el tablero
   * la marca para que las opciones y lo dibujado coincidan. Las opciones llegan
   * aparte, así que se anota la firma para no recalcular otra vez.
   */
  protected aplicarEstado(estado: EstadoColocacion): void {
    const marcas: Record<string, 'propio' | 'rival'> = {};
    for (const v of estado.ocupados ?? []) marcas[v] = 'rival';
    if (estado.mio) marcas[estado.mio] = 'propio';
    this.marcas.set(marcas);
    this.firmaRespuesta = firma(marcas, this.jugadores());
  }

  /** El asistente pidió otra recomendación: el tablero y la franja pasan a ella. */
  protected aplicarOpcionesNuevas(opciones: Opcion[]): void {
    this.respuesta.update((r) =>
      r ? { ...r, opciones, momento: this.mio() ? 'segunda' : 'primera' } : r,
    );
    this.seleccionada.set(0);
  }

  private recalcular(motivo: 'boton' | 'marcas'): void {
    const tablero = this.tablero();
    if (!tablero) return;
    const marcas = this.marcas();
    const firmaPedida = firma(marcas, this.jugadores());

    if (this.completo()) {
      // Con los dos poblados puestos no hay nada que recomendar; el panel lo dice.
      this.respuesta.set(null);
      this.firmaRespuesta = firmaPedida;
      return;
    }

    const pedido = ++this.pedido;
    this.recomendando.set(true);
    this.errorRecomendar.set(null);
    this.api
      .recomendar({
        tablero,
        jugadores: this.jugadores(),
        ocupados: this.ocupados(),
        mio: this.mio(),
        cuantas: 3,
      })
      .subscribe({
        next: (respuesta) => {
          if (pedido !== this.pedido) return;
          this.firmaRespuesta = firmaPedida;
          this.respuesta.set(respuesta);
          this.seleccionada.set(0);
          this.recomendando.set(false);
          if (motivo === 'boton') {
            this.conversacion.update((n) => n + 1);
          } else {
            this.actualizacion.update((a) => ({
              n: (a?.n ?? 0) + 1,
              texto: respuesta.momento === 'segunda'
                ? 'Actualicé las opciones: tu primer poblado ya está; estas son las mejores para el **segundo**.'
                : 'Actualicé las opciones con los poblados marcados en el tablero.',
            }));
          }
        },
        error: (e: HttpErrorResponse) => {
          if (pedido !== this.pedido) return;
          // Las opciones anteriores pueden ya no ser legales: no se dejan en pantalla.
          this.firmaRespuesta = firmaPedida;
          this.respuesta.set(null);
          this.errorRecomendar.set(mensajeDeError(e));
          this.recomendando.set(false);
        },
      });
  }

  private avisar(texto: string): void {
    this.aviso.set(texto);
    clearTimeout(this.temporizadorAviso);
    this.temporizadorAviso = setTimeout(() => this.aviso.set(null), DURACION_AVISO_MS);
  }
}

/** Traduce un fallo HTTP a una frase que el usuario pueda entender. */
function mensajeDeError(e: HttpErrorResponse): string {
  if (e.status === 0) {
    return 'No hay conexión con el servidor. Revisa que el backend esté encendido.';
  }
  if (e.status === 503) {
    return 'El modelo no está disponible en el servidor; el tablero sí funciona, pero no se puede recomendar.';
  }
  // Los errores de dominio llegan como {error, detalle} (backend/app/core/errors.py).
  const { error, detalle } = e.error ?? {};
  if (typeof error === 'string') {
    return typeof detalle === 'string' ? `${error}. ${detalle}` : error;
  }
  return `El servidor respondió con un error (${e.status}).`;
}
