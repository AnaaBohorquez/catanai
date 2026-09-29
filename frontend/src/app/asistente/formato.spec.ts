import { bloquesDe } from './formato';

describe('bloquesDe', () => {
  it('reconoce título, subtítulo, listas y Haz/Evita', () => {
    const texto = [
      '### Expansión · Opción 1 · ≈ 8.6 pts',
      'Creces a lo ancho.',
      '',
      '**Plan**',
      '1. Camino — en unas 2.2 rondas',
      '2. Poblado',
      '',
      '- madera y ladrillo a la vez',
      'Haz: tiende caminos pronto.',
      '**Evita:** subir a ciudad muy temprano.',
    ].join('\n');
    expect(bloquesDe(texto)).toEqual([
      { tipo: 'titulo', texto: 'Expansión · Opción 1 · ≈ 8.6 pts', icono: '🛤️' },
      { tipo: 'parrafo', texto: 'Creces a lo ancho.' },
      { tipo: 'subtitulo', texto: 'Plan' },
      { tipo: 'lista', ordenada: true, elementos: ['Camino — en unas 2.2 rondas', 'Poblado'] },
      { tipo: 'lista', ordenada: false, elementos: ['madera y ladrillo a la vez'] },
      { tipo: 'haz', texto: 'tiende caminos pronto.' },
      { tipo: 'evita', texto: 'subir a ciudad muy temprano.' },
    ]);
  });

  it('un texto corrido queda como un solo párrafo', () => {
    expect(bloquesDe('Una ciudad cuesta\n2 trigo y 3 mineral.')).toEqual([
      { tipo: 'parrafo', texto: 'Una ciudad cuesta 2 trigo y 3 mineral.' },
    ]);
  });

  it('no duplica el icono si el título ya trae uno', () => {
    expect(bloquesDe('### 🏰 Ciudades y desarrollo')[0]).toEqual({
      tipo: 'titulo',
      texto: '🏰 Ciudades y desarrollo',
      icono: null,
    });
  });

  it('una negrita dentro de la frase no es subtítulo', () => {
    expect(bloquesDe('Elegiste **Expansión** por su madera.')[0].tipo).toBe('parrafo');
  });
});
