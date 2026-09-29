import type { Hexagono, Tablero } from '../api/tipos';
import { aristasDeCosta, clave, destinosPosibles, girarPuertos } from './costa';
import { FICHAS_BASE, conteoFichas, pipsDe, reacomodar, sinNumero } from './reparto';

/** Las 19 coordenadas del juego base. */
function coordenadas(): [number, number][] {
  const salida: [number, number][] = [];
  for (let q = -2; q <= 2; q++) {
    for (let r = -2; r <= 2; r++) {
      if (Math.abs(q + r) <= 2) salida.push([q, r]);
    }
  }
  return salida;
}

/** Un tablero mínimo con sus 72 aristas, construidas como en el backend. */
function tableroDePrueba(): Tablero {
  const direcciones = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]];
  const id = (hs: [number, number][]) =>
    hs
      .slice()
      .sort((a, b) => a[0] - b[0] || a[1] - b[1])
      .map(([q, r]) => `${q},${r}`)
      .join('|');
  const vertices = new Set<string>();
  const aristas = new Set<string>();
  for (const [q, r] of coordenadas()) {
    const vs = direcciones.map(([dq, dr], i) => {
      const [eq, er] = direcciones[(i + 1) % 6];
      return id([[q, r], [q + dq, r + dr], [q + eq, r + er]]);
    });
    vs.forEach((v, i) => {
      vertices.add(v);
      aristas.add([v, vs[(i + 1) % 6]].sort().join('~'));
    });
  }
  return {
    hexagonos: coordenadas().map(([q, r]) => ({
      id: `${q},${r}`, q, r, terreno: 'bosque', pips: 0,
    })) as Hexagono[],
    puertos: [],
    vertices: [...vertices].map((v) => ({ id: v, hexagonos: [] })),
    aristas: [...aristas].map((a) => ({ vertices: a.split('~') })),
  } as unknown as Tablero;
}

describe('costa', () => {
  const tablero = tableroDePrueba();

  it('tiene 72 aristas y 30 de costa, consecutivas', () => {
    expect(tablero.aristas.length).toBe(72);
    const costa = aristasDeCosta(tablero);
    expect(costa.length).toBe(30);
    costa.forEach((a, i) => {
      const siguiente = costa[(i + 1) % costa.length];
      expect(a.some((v) => siguiente.includes(v))).toBe(true);
    });
  });

  it('seis giros devuelven los puertos a su lugar', () => {
    const costa = aristasDeCosta(tablero);
    let actual: Tablero = { ...tablero, puertos: [{ vertices: costa[0], tipo: '3:1' }] };
    for (let i = 0; i < 6; i++) actual = { ...actual, puertos: girarPuertos(actual) };
    expect(clave(actual.puertos[0].vertices)).toBe(clave(costa[0]));
  });

  it('no deja mover un puerto junto a otro', () => {
    const costa = aristasDeCosta(tablero);
    const conDos: Tablero = {
      ...tablero,
      puertos: [{ vertices: costa[0], tipo: '3:1' }, { vertices: costa[10], tipo: 'trigo' }],
    };
    const destinos = destinosPosibles(conDos, 0).map(clave);
    expect(destinos).not.toContain(clave(costa[10]));
    expect(destinos).not.toContain(clave(costa[9]));
    expect(destinos).toContain(clave(costa[0]));
  });
});

describe('reparto', () => {
  it('los pips salen de la fórmula 6 − |7 − n|', () => {
    expect([2, 6, 8, 12].map(pipsDe)).toEqual([1, 5, 5, 1]);
    expect(pipsDe(null)).toBe(0);
  });

  it('hay 18 fichas en el juego base', () => {
    expect(Object.values(FICHAS_BASE).reduce((a, b) => a + b, 0)).toBe(18);
  });

  it('cuenta fichas y detecta los hexágonos sin número', () => {
    const hexagonos = [
      { id: 'a', terreno: 'bosque', numero: 6 },
      { id: 'b', terreno: 'campos', numero: null },
      { id: 'c', terreno: 'desierto', numero: null },
    ] as Hexagono[];
    expect(conteoFichas(hexagonos).find((c) => c.clave === 6)?.hay).toBe(1);
    expect(sinNumero(hexagonos).map((h) => h.id)).toEqual(['b']);
  });
});

describe('reacomodar', () => {
  const hex = (id: string, terreno: Hexagono['terreno'], numero: number | null): Hexagono =>
    ({ id, q: 0, r: 0, terreno, numero, pips: pipsDe(numero), recurso: null }) as Hexagono;

  it('al poner un número que ya estaba completo, mueve la otra ficha a su siguiente opción', () => {
    const hs = [hex('a', 'bosque', 9), hex('b', 'bosque', 9), hex('c', 'campos', 9)];
    const opciones = {
      a: { numeros: [9, 4], terrenos: ['bosque' as const] },
      b: { numeros: [4, 9], terrenos: ['bosque' as const] },
      c: { numeros: [9, 3], terrenos: ['campos' as const] },
    };
    // El usuario confirma la c como 9: sobra un 9; b tenía el 9 como 2.ª opción.
    const { hexagonos, cambios } = reacomodar(hs, 'c', new Set(['c']), opciones);
    expect(hexagonos.map((h) => h.numero)).toEqual([9, 4, 9]);
    expect(hexagonos[1].pips).toBe(3);
    expect(cambios).toEqual(['9 → 4']);
  });

  it('no mueve lo que el usuario ya revisó', () => {
    const hs = [hex('a', 'bosque', 9), hex('b', 'bosque', 9), hex('c', 'campos', 9)];
    const opciones = {
      a: { numeros: [9, 4], terrenos: ['bosque' as const] },
      b: { numeros: [4, 9], terrenos: ['bosque' as const] },
      c: { numeros: [9, 3], terrenos: ['campos' as const] },
    };
    const { hexagonos } = reacomodar(hs, 'c', new Set(['c', 'a', 'b']), opciones);
    expect(hexagonos.map((h) => h.numero)).toEqual([9, 9, 9]);
  });

  it('al mover el desierto, el viejo desierto recibe terreno y el número que sobró', () => {
    const hs = [hex('d', 'desierto', null), hex('x', 'desierto', null)];
    const opciones = {
      d: { numeros: [5, 6], terrenos: ['desierto' as const, 'campos' as const] },
      x: { numeros: [], terrenos: ['campos' as const, 'desierto' as const] },
    };
    // El usuario dice que x es el desierto (antes era un campo con 5).
    const { hexagonos } = reacomodar(hs, 'x', new Set(['x']), opciones);
    expect(hexagonos[0].terreno).toBe('campos');
    expect(hexagonos[0].numero).toBe(5);
  });
});
