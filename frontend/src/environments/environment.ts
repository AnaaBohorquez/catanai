/**
 * Configuración de producción (`npm run build`, la que despliega Vercel).
 *
 * Frontend y backend se publican en el mismo dominio con Vercel Services: el
 * `vercel.json` de la raíz manda `/api/...` al backend. Por eso basta una ruta relativa.
 */
export const environment = {
  apiUrl: '/api/v1',
};
