/**
 * Geometría del tablero: de coordenadas axiales a píxeles.
 *
 * Funciones puras, sin nada de Angular, para poder probarlas solas. La convención
 * coincide con `DIRECCIONES` de `backend/app/domain/tablero.py`: hexágonos con la
 * punta hacia arriba y filas horizontales de 3-4-5-4-3.
 */

export interface Punto {
  x: number;
  y: number;
}

const RAIZ3 = Math.sqrt(3);

/** Convierte el identificador `"q,r"` del backend en números. */
export function leerCoordenada(id: string): [number, number] {
  const [q, r] = id.split(',').map(Number);
  return [q, r];
}

/**
 * Centro de un hexágono en píxeles.
 *
 * Avanzar una columna (`q`) mueve √3·tam a la derecha; bajar una fila (`r`) mueve
 * 1.5·tam hacia abajo y media columna a la derecha, por eso aparece `r / 2`.
 */
export function centroHex(q: number, r: number, tam: number): Punto {
  return { x: tam * RAIZ3 * (q + r / 2), y: tam * 1.5 * r };
}

/** Las seis esquinas del hexágono, en el formato del atributo `points` de SVG. */
export function esquinasHex(centro: Punto, tam: number): string {
  const esquinas: string[] = [];
  for (let i = 0; i < 6; i++) {
    // Punta arriba: la primera esquina está a -90° y cada una gira 60°.
    const angulo = (Math.PI / 180) * (60 * i - 90);
    const x = centro.x + tam * Math.cos(angulo);
    const y = centro.y + tam * Math.sin(angulo);
    esquinas.push(`${x.toFixed(2)},${y.toFixed(2)}`);
  }
  return esquinas.join(' ');
}

/**
 * Posición de un vértice a partir de su identificador, por ejemplo `-1,0|0,-1|0,0`.
 *
 * Un vértice es el conjunto de los tres hexágonos que toca (algunos pueden ser mar),
 * y la esquina que comparten cae justo en el promedio de sus tres centros.
 */
export function centroVertice(id: string, tam: number): Punto {
  const centros = id.split('|').map((h) => centroHex(...leerCoordenada(h), tam));
  return {
    x: centros.reduce((s, c) => s + c.x, 0) / centros.length,
    y: centros.reduce((s, c) => s + c.y, 0) / centros.length,
  };
}

/** Posiciones de los puntitos de pips, centrados en una fila bajo el número. */
export function puntosPips(pips: number, centro: Punto, tam: number): Punto[] {
  const separacion = tam * 0.1;
  const inicio = centro.x - ((pips - 1) * separacion) / 2;
  return Array.from({ length: pips }, (_, i) => ({
    x: inicio + i * separacion,
    y: centro.y + tam * 0.2,
  }));
}

/**
 * Dónde dibujar un puerto: un poco hacia el mar desde la arista que ocupa.
 *
 * Los dos vértices de la arista comparten dos hexágonos; el que no está en el
 * tablero es el mar, y hacia su centro se desplaza la marca del puerto.
 */
export function posicionPuerto(
  vertices: string[],
  hexagonosDelTablero: Set<string>,
  tam: number,
): Punto {
  const [a, b] = vertices.map((v) => v.split('|'));
  const compartidos = a.filter((h) => b.includes(h));
  const mar = compartidos.find((h) => !hexagonosDelTablero.has(h)) ?? compartidos[0];
  const [pa, pb] = vertices.map((v) => centroVertice(v, tam));
  const medio = { x: (pa.x + pb.x) / 2, y: (pa.y + pb.y) / 2 };
  const centroMar = centroHex(...leerCoordenada(mar), tam);
  return {
    x: medio.x + (centroMar.x - medio.x) * 0.55,
    y: medio.y + (centroMar.y - medio.y) * 0.55,
  };
}
