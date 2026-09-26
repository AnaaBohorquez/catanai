import { centroHex, centroVertice, posicionPuerto, puntosPips } from './geometria';

const TAM = 50;

/** Las 19 coordenadas del juego base: todas las (q, r) con |q|, |r|, |q+r| ≤ 2. */
function coordenadasBase(): [number, number][] {
  const salida: [number, number][] = [];
  for (let q = -2; q <= 2; q++) {
    for (let r = -2; r <= 2; r++) {
      if (Math.abs(q + r) <= 2) salida.push([q, r]);
    }
  }
  return salida;
}

const distancia = (a: { x: number; y: number }, b: { x: number; y: number }) =>
  Math.hypot(a.x - b.x, a.y - b.y);

describe('geometria', () => {
  it('coloca los 19 hexágonos en centros distintos', () => {
    const centros = coordenadasBase().map(([q, r]) => centroHex(q, r, TAM));
    const unicos = new Set(centros.map((c) => `${c.x.toFixed(3)},${c.y.toFixed(3)}`));
    expect(centros.length).toBe(19);
    expect(unicos.size).toBe(19);
  });

  it('pone a los seis vecinos a la misma distancia, tam·√3', () => {
    const direcciones = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]];
    const origen = centroHex(0, 0, TAM);
    for (const [dq, dr] of direcciones) {
      expect(distancia(origen, centroHex(dq, dr, TAM))).toBeCloseTo(TAM * Math.sqrt(3));
    }
  });

  it('pone cada vértice a distancia tam de los centros de sus tres hexágonos', () => {
    const vertice = centroVertice('-1,0|0,-1|0,0', TAM);
    for (const [q, r] of [[-1, 0], [0, -1], [0, 0]]) {
      expect(distancia(vertice, centroHex(q, r, TAM))).toBeCloseTo(TAM);
    }
  });

  it('dibuja tantos puntitos como pips', () => {
    expect(puntosPips(5, { x: 0, y: 0 }, TAM)).toHaveLength(5);
    expect(puntosPips(1, { x: 0, y: 0 }, TAM)[0].x).toBeCloseTo(0);
  });

  it('empuja el puerto hacia el hexágono de mar', () => {
    // Arista entre (0,-2) en el tablero y (0,-3) en el mar.
    const tablero = new Set(coordenadasBase().map(([q, r]) => `${q},${r}`));
    const puerto = posicionPuerto(['-1,-2|0,-3|0,-2', '0,-2|0,-3|1,-3'], tablero, TAM);
    const mar = centroHex(0, -3, TAM);
    const tierra = centroHex(0, -2, TAM);
    expect(distancia(puerto, mar)).toBeLessThan(distancia(puerto, tierra));
  });
});
