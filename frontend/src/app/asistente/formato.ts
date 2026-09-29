/**
 * Formato de las respuestas del asistente: un subconjunto mínimo de Markdown que se
 * dibuja con el mismo estilo que las tarjetas de recomendación.
 *
 * El texto se convierte en datos (bloques) y la plantilla de Angular los dibuja; nunca
 * se inserta como HTML, así que lo que escriba el modelo de lenguaje no puede meter
 * etiquetas ni scripts en la página.
 *
 * Lo que se reconoce, línea por línea:
 * - `### Título`            → encabezado, con el icono de la familia si la nombra;
 * - `**Subtítulo**` sola     → subtítulo de sección ("Plan", "Por qué");
 * - `- elemento`             → lista con viñetas;
 * - `1. elemento`            → lista numerada;
 * - `Haz: …` / `Evita: …`    → línea destacada, como en las tarjetas;
 * - cualquier otra línea     → párrafo (las líneas seguidas se juntan).
 */
import { ICONO_ESTRATEGIA } from '../estilo-catan';

export type Bloque =
  | { tipo: 'titulo'; texto: string; icono: string | null }
  | { tipo: 'subtitulo'; texto: string }
  | { tipo: 'lista'; ordenada: boolean; elementos: string[] }
  | { tipo: 'haz' | 'evita'; texto: string }
  | { tipo: 'parrafo'; texto: string };

/** Qué palabra de un título delata cada familia de estrategia. */
const FAMILIA_EN_TITULO: [RegExp, string][] = [
  [/expansi[oó]n/i, 'expansion'],
  [/ciudades/i, 'ciudades'],
  [/puerto/i, 'puerto'],
  [/desequilibrad/i, 'desequilibrada'],
];

const VINETA = /^\s*[-*•]\s+(.*)$/;
const NUMERADA = /^\s*\d+[.)]\s+(.*)$/;
const DESTACADA = /^\s*(?:\*\*)?(haz|evita)(?:\*\*)?\s*:\s*(?:\*\*)?\s*(.*)$/i;
const SUBTITULO = /^\s*\*\*([^*]+?):?\*\*\s*:?\s*$/;
/** Un emoji al inicio: si el título ya trae uno, no se le agrega otro. */
const EMPIEZA_CON_EMOJI = /^\p{Extended_Pictographic}/u;

export function bloquesDe(texto: string): Bloque[] {
  const bloques: Bloque[] = [];
  const agregarALista = (ordenada: boolean, elemento: string) => {
    const ultimo = bloques.at(-1);
    if (ultimo?.tipo === 'lista' && ultimo.ordenada === ordenada) {
      ultimo.elementos.push(elemento);
    } else {
      bloques.push({ tipo: 'lista', ordenada, elementos: [elemento] });
    }
  };

  let parrafoAbierto = false;
  for (const linea of texto.split('\n')) {
    const limpia = linea.trim();
    if (!limpia) {
      parrafoAbierto = false;
      continue;
    }
    let m: RegExpMatchArray | null;
    if (limpia.startsWith('#')) {
      const titulo = limpia.replace(/^#+\s*/, '');
      bloques.push({ tipo: 'titulo', texto: titulo, icono: iconoDe(titulo) });
      parrafoAbierto = false;
    } else if ((m = limpia.match(DESTACADA))) {
      const tipo = m[1].toLowerCase() === 'haz' ? 'haz' : 'evita';
      bloques.push({ tipo, texto: m[2].replace(/\*\*$/, '').trim() });
      parrafoAbierto = false;
    } else if ((m = limpia.match(SUBTITULO))) {
      bloques.push({ tipo: 'subtitulo', texto: m[1].trim() });
      parrafoAbierto = false;
    } else if ((m = limpia.match(VINETA))) {
      agregarALista(false, m[1]);
      parrafoAbierto = false;
    } else if ((m = limpia.match(NUMERADA))) {
      agregarALista(true, m[1]);
      parrafoAbierto = false;
    } else {
      const ultimo = bloques.at(-1);
      if (parrafoAbierto && ultimo?.tipo === 'parrafo') {
        ultimo.texto += ' ' + limpia;
      } else {
        bloques.push({ tipo: 'parrafo', texto: limpia });
      }
      parrafoAbierto = true;
    }
  }
  return bloques;
}

function iconoDe(titulo: string): string | null {
  if (EMPIEZA_CON_EMOJI.test(titulo)) return null;
  const familia = FAMILIA_EN_TITULO.find(([patron]) => patron.test(titulo))?.[1];
  return familia ? ICONO_ESTRATEGIA[familia] : null;
}
