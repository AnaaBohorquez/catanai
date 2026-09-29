import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import type { WritableSignal } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import type { RespuestaRecomendar, Tablero } from './api/tipos';

import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
  });

  it('se crea', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('muestra el título', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Colono IA');
  });

  describe('Nueva partida', () => {
    const tablero = { hexagonos: [], vertices: [], puertos: [] } as unknown as Tablero;

    /** Un tablero con marcas y opciones, como a mitad de una colocación. */
    function enCurso() {
      const app = TestBed.createComponent(App).componentInstance as unknown as Internos;
      app.tablero.set(tablero);
      app.marcas.set({ a: 'rival' });
      app.respuesta.set({ momento: 'primera', opciones: [], parejas_evaluadas: 1, avisos: [] });
      app.seleccionada.set(2);
      return app;
    }

    it('una nueva colocación conserva el tablero y borra lo demás', () => {
      const app = enCurso();
      const conversacion = app.conversacion();
      app.nuevaColocacion();
      expect(app.tablero()).toBe(tablero);
      expect(app.marcas()).toEqual({});
      expect(app.respuesta()).toBeNull();
      expect(app.seleccionada()).toBe(0);
      expect(app.conversacion()).toBe(conversacion + 1);
    });

    it('empezar de cero quita también el tablero', () => {
      const app = enCurso();
      app.nuevaPartidaAbierta.set(true);
      app.empezarDeCero();
      expect(app.tablero()).toBeNull();
      expect(app.marcas()).toEqual({});
      expect(app.nuevaPartidaAbierta()).toBe(false);
    });
  });
});

/** Lo protegido de App que tocan estas pruebas. */
interface Internos {
  tablero: WritableSignal<Tablero | null>;
  marcas: WritableSignal<Record<string, string>>;
  respuesta: WritableSignal<RespuestaRecomendar | null>;
  seleccionada: WritableSignal<number>;
  conversacion: WritableSignal<number>;
  nuevaPartidaAbierta: WritableSignal<boolean>;
  nuevaColocacion(): void;
  empezarDeCero(): void;
}
