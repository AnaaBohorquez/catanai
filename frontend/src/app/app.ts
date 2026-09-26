import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { timeout } from 'rxjs';

import { ColonoApi } from './api/colono-api';
import type { Opcion, RespuestaRecomendar, Tablero } from './api/tipos';
import { AsistenteComponent } from './asistente/asistente';
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

@Component({
  imports: [TableroComponent, AsistenteComponent],
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
   * Sube cada vez que empieza una conversación nueva: otro tablero, otra
   * recomendación u otro número de jugadores. Las opciones que pide el propio
   * asistente no la cambian, para no borrar lo que se estaba hablando.
   */
  protected readonly conversacion = signal(0);

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
        // Las opciones anteriores eran de otro tablero: ya no valen.
        this.respuesta.set(null);
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

  protected cambiarJugadores(n: number): void {
    if (n === this.jugadores()) return;
    this.jugadores.set(n);
    // Las cifras dependen del número de jugadores: las anteriores ya no aplican.
    this.respuesta.set(null);
    this.conversacion.update((n) => n + 1);
  }

  /** El asistente pidió otra recomendación: el tablero y la franja pasan a ella. */
  protected aplicarOpcionesNuevas(opciones: Opcion[]): void {
    this.respuesta.update((r) => (r ? { ...r, opciones } : r));
    this.seleccionada.set(0);
  }

  protected pedirRecomendacion(): void {
    const tablero = this.tablero();
    if (!tablero) return;
    this.recomendando.set(true);
    this.errorRecomendar.set(null);
    this.api
      .recomendar({ tablero, jugadores: this.jugadores(), ocupados: [], cuantas: 3 })
      .subscribe({
        next: (respuesta) => {
          this.respuesta.set(respuesta);
          this.seleccionada.set(0);
          this.conversacion.update((n) => n + 1);
          this.recomendando.set(false);
        },
        error: (e: HttpErrorResponse) => {
          this.errorRecomendar.set(mensajeDeError(e));
          this.recomendando.set(false);
        },
      });
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
