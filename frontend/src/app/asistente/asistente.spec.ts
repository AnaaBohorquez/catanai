import { trocear } from './asistente';

describe('trocear', () => {
  it('separa las negritas marcadas con **', () => {
    expect(trocear('Elegiste **Expansión**, que estima 8.3')).toEqual([
      { texto: 'Elegiste ', negrita: false },
      { texto: 'Expansión', negrita: true },
      { texto: ', que estima 8.3', negrita: false },
    ]);
  });

  it('deja intacto un texto sin marcas', () => {
    expect(trocear('Sin negritas')).toEqual([{ texto: 'Sin negritas', negrita: false }]);
  });
});
