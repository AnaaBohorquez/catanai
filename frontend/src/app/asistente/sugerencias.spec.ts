import { type Contexto, PREGUNTA_CRECER, sugerir, temaDe } from './sugerencias';

const base: Contexto = {
  fase: 'colocacion',
  tema: 'inicio',
  seleccionada: 1,
  total: 3,
  familia: 'expansion',
  otraFamilia: 'Ciudades',
  tienePuerto: false,
  preguntadas: [],
};

describe('temaDe', () => {
  it('reconoce el tema por los títulos de la respuesta', () => {
    expect(temaDe('### Expansión · Opción 1\n**Cómo se gana**\n…')).toBe('estrategia');
    expect(temaDe('### Expansión\n**Por qué**\n- …')).toBe('porque');
    expect(temaDe('…\n### Expansión · Opción 1\n…\n### Ciudades · Opción 2')).toBe('comparar');
    expect(temaDe('### Tu partida · 2 poblados')).toBe('produccion');
    expect(temaDe('Estos son…\n### Destino A · …')).toBe('crecer');
    expect(temaDe('### 📘 Los pips')).toBe('concepto');
  });

  it('si la respuesta no tiene forma, usa la pregunta', () => {
    expect(temaDe('Texto libre', '¿Compárala con la 2?')).toBe('comparar');
  });
});

describe('sugerir', () => {
  it('tras la estrategia propone el siguiente paso y otra vía', () => {
    const s = sugerir({ ...base, tema: 'estrategia' });
    expect(s).toContain('¿Qué recurso me va a faltar?');
    expect(s).toContain('¿Y si juego Ciudades?');
  });

  it('siempre trae una pregunta para aprender, acorde a la familia', () => {
    const s = sugerir({ ...base, tema: 'estrategia' });
    expect(s.at(-1)).toBe('📘 ¿Por qué madera y ladrillo van juntos?');
    expect(sugerir({ ...base, familia: 'puerto' }).at(-1)).toBe('📘 ¿Cómo funciona un puerto 2:1?');
  });

  it('no repite lo que ya se preguntó, aunque cambien acentos o signos', () => {
    const s = sugerir({
      ...base,
      tema: 'estrategia',
      preguntadas: ['que recurso me va a faltar', '📘 ¿Por qué madera y ladrillo van juntos?'],
    });
    expect(s).not.toContain('¿Qué recurso me va a faltar?');
    expect(s).not.toContain('📘 ¿Por qué madera y ladrillo van juntos?');
    expect(s.length).toBe(4);
  });

  it('en partida sugiere preguntas de partida', () => {
    const s = sugerir({ ...base, fase: 'partida', tema: 'produccion' });
    expect(s).toContain('¿Cómo consigo lo que no produzco?');
    expect(s).toContain(PREGUNTA_CRECER);
    expect(s.at(-1)).toBe('📘 ¿Para qué sirve una ciudad?');
  });

  it('sin opciones no sugiere nada', () => {
    expect(sugerir({ ...base, fase: 'sin-opciones' })).toEqual([]);
  });
});
