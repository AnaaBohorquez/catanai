import { MAX_POBLADOS, type Marcas, tocar } from './colocacion';

const nada = new Set<string>();

describe('tocar', () => {
  it('deja poner más de dos poblados propios (partida en curso)', () => {
    const marcas: Marcas = { a: 'propio', b: 'propio' };
    expect(tocar(marcas, 'c', 'propio', nada)).toEqual({
      marcas: { a: 'propio', b: 'propio', c: 'propio' },
    });
  });

  it('respeta el máximo de poblados del juego', () => {
    const marcas: Marcas = Object.fromEntries(
      Array.from({ length: MAX_POBLADOS }, (_, i) => [`p${i}`, 'propio' as const]),
    );
    expect(tocar(marcas, 'x', 'propio', nada)).toHaveProperty('aviso');
  });

  it('sube un poblado propio a ciudad y la baja al tocarla otra vez', () => {
    const ciudad = tocar({ a: 'propio' }, 'a', 'ciudad', nada);
    expect(ciudad).toEqual({ marcas: { a: 'ciudad' } });
    expect(tocar({ a: 'ciudad' }, 'a', 'ciudad', nada)).toEqual({ marcas: { a: 'propio' } });
  });

  it('una ciudad solo sale de un poblado tuyo', () => {
    expect(tocar({ a: 'rival' }, 'a', 'ciudad', nada)).toHaveProperty('aviso');
    expect(tocar({}, 'a', 'ciudad', nada)).toHaveProperty('aviso');
  });

  it('aplica la regla de distancia', () => {
    expect(tocar({}, 'a', 'rival', new Set(['a']))).toHaveProperty('aviso');
  });

  it('borrar quita cualquier marca', () => {
    expect(tocar({ a: 'ciudad', b: 'rival' }, 'a', 'borrar', nada)).toEqual({ marcas: { b: 'rival' } });
  });
});
