/**
 * Qué preguntas sugiere el chat después de cada respuesta.
 *
 * La idea es didáctica: en vez de repetir siempre las mismas, el chat propone el
 * siguiente paso natural según el tema de la última respuesta, nunca repite una
 * pregunta ya hecha y añade una pregunta «para aprender» (📘) que explica un concepto
 * del juego. Todas tienen respuesta también en el modo básico (plantillas).
 */

/** De qué trató la última respuesta del asistente. */
export type Tema =
  | 'inicio'
  | 'estrategia'
  | 'porque'
  | 'comparar'
  | 'conseguir'
  | 'concepto'
  | 'produccion'
  | 'crecer'
  | 'otro';

export interface Contexto {
  /** Sin opciones en pantalla, colocación inicial o partida en curso. */
  fase: 'sin-opciones' | 'colocacion' | 'partida';
  tema: Tema;
  /** Opción seleccionada, desde 1, y cuántas hay. */
  seleccionada: number;
  total: number;
  /** Familia de la opción seleccionada (expansion, ciudades, puerto…). */
  familia: string | null;
  /** Otra familia en pantalla, con el nombre corto con que se pregunta por ella. */
  otraFamilia: string | null;
  tienePuerto: boolean;
  /** Lo que el usuario ya preguntó en esta conversación. */
  preguntadas: string[];
}

export const PREGUNTA_CRECER = '🧭 ¿Hacia dónde crezco?';

/** Preguntas para aprender: un concepto del juego cada una. */
const CONCEPTOS = {
  pips: '📘 ¿Qué son los pips?',
  puerto: '📘 ¿Cómo funciona un puerto 2:1?',
  ciudad: '📘 ¿Para qué sirve una ciudad?',
  maderaLadrillo: '📘 ¿Por qué madera y ladrillo van juntos?',
} as const;

/** Nombre corto de cada familia, como lo entiende el chat ("¿Y si juego Ciudades?"). */
export const NOMBRE_CORTO_FAMILIA: Record<string, string> = {
  expansion: 'Expansión',
  ciudades: 'Ciudades',
  puerto: 'Puerto',
};

/** Cuántas sugerencias de seguimiento, más una para aprender. */
const SEGUIMIENTO = 3;

/** Reconoce el tema por la forma de la respuesta (sus títulos) y, si no, por la pregunta. */
export function temaDe(respuesta: string, pregunta = ''): Tema {
  const titulos = respuesta.match(/^###\s.*$/gm) ?? [];
  if (/^###\s*📘/m.test(respuesta)) return 'concepto';
  if (titulos.some((t) => t.includes('Tu partida'))) return 'produccion';
  if (titulos.some((t) => t.includes('Destino'))) return 'crecer';
  if (titulos.some((t) => t.includes('Cómo conseguir'))) return 'conseguir';
  if (titulos.length >= 2) return 'comparar';
  if (respuesta.includes('**Cómo se gana**') || respuesta.includes('**Plan**')) return 'estrategia';
  if (respuesta.includes('**Por qué**')) return 'porque';

  const p = normalizar(pregunta);
  if (/compar|diferencia/.test(p)) return 'comparar';
  if (/estrategia|como juego|plan/.test(p)) return 'estrategia';
  if (/por que/.test(p)) return 'porque';
  if (/consig|falta/.test(p)) return 'conseguir';
  if (/construyo|produc/.test(p)) return 'produccion';
  if (/crezco|crecer|destino/.test(p)) return 'crecer';
  return 'otro';
}

export function sugerir(c: Contexto): string[] {
  if (c.fase === 'sin-opciones') return [];
  const hechas = new Set(c.preguntadas.map(normalizar));
  const nueva = (q: string) => !hechas.has(normalizar(q));

  const seguimiento = (c.fase === 'partida' ? deLaPartida(c) : deLaColocacion(c)).filter(nueva);
  const general = { ...c, tema: 'inicio' as const };
  const base = (c.fase === 'partida' ? deLaPartida(general) : deLaColocacion(general)).filter(nueva);
  const elegidas = unicas([...seguimiento, ...base]).slice(0, SEGUIMIENTO);

  const aprender = conceptosPara(c).find(nueva);
  return aprender ? [...elegidas, aprender] : elegidas;
}

function deLaColocacion(c: Contexto): string[] {
  const n = c.seleccionada;
  const otra = n === 1 ? 2 : 1;
  const comparar = c.total > 1 ? [`Compárala con la opción ${otra}`] : [];
  const otraVia = c.otraFamilia ? [`¿Y si juego ${c.otraFamilia}?`] : [];
  switch (c.tema) {
    case 'estrategia':
      return ['¿Qué recurso me va a faltar?', ...otraVia, '¿Y si me quitan un vértice?'];
    case 'porque':
      return ['¿Qué estrategia sigo?', ...comparar, '¿Por qué no elegir la de más pips?'];
    case 'comparar':
      return ['¿Qué estrategia sigo?', '¿Qué recurso me va a faltar?', '¿Y si me quitan un vértice?'];
    case 'conseguir':
      return ['¿Qué estrategia sigo?', `¿Por qué la opción ${n}?`, ...otraVia];
    default:
      return [`¿Por qué la opción ${n}?`, '¿Qué estrategia sigo?', ...comparar, '¿Y si me quitan un vértice?'];
  }
}

function deLaPartida(c: Contexto): string[] {
  switch (c.tema) {
    case 'produccion':
      return ['¿Cómo consigo lo que no produzco?', PREGUNTA_CRECER, '¿Me conviene una ciudad o un poblado?'];
    case 'crecer':
      return ['¿Qué construyo ahora?', '¿Cómo consigo lo que no produzco?', '¿Qué me falta para una ciudad?'];
    case 'conseguir':
      return ['¿Qué construyo ahora?', PREGUNTA_CRECER, '¿Me conviene una ciudad o un poblado?'];
    default:
      return ['¿Qué construyo ahora?', PREGUNTA_CRECER, '¿Qué me falta para una ciudad?'];
  }
}

/** Los conceptos, del más al menos relacionado con la situación. */
function conceptosPara(c: Contexto): string[] {
  const orden: string[] = [];
  if (c.fase === 'partida') orden.push(CONCEPTOS.ciudad);
  if (c.tienePuerto || c.familia === 'puerto') orden.push(CONCEPTOS.puerto);
  if (c.familia === 'expansion') orden.push(CONCEPTOS.maderaLadrillo);
  if (c.familia === 'ciudades') orden.push(CONCEPTOS.ciudad);
  orden.push(CONCEPTOS.pips, CONCEPTOS.maderaLadrillo, CONCEPTOS.ciudad, CONCEPTOS.puerto);
  return unicas(orden);
}

function unicas(lista: string[]): string[] {
  return [...new Set(lista)];
}

/** Minúsculas, sin acentos, emojis ni signos: así se reconoce una pregunta ya hecha. */
export function normalizar(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}
