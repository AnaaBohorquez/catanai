# Despliegue

La app pública tiene dos piezas en dos servicios gratuitos:

| Pieza | Servicio | Qué sirve |
|---|---|---|
| Backend (FastAPI + modelo) | Render, *Web Service* con Python nativo | `https://<servicio>.onrender.com/api/v1` |
| Frontend (Angular compilado) | Vercel | `https://<proyecto>.vercel.app` |

El frontend es un conjunto de archivos estáticos (HTML, JS, CSS) que corre en el
navegador del usuario. Es el navegador el que llama al backend, y por eso el backend
tiene que autorizar el dominio de Vercel en CORS.

Los dos servicios leen el repositorio de GitHub. **Cada `git push` a `main` vuelve a
desplegar ambos automáticamente.**

---

## Render (backend)

| Campo | Valor | Por qué |
|---|---|---|
| Name | `colono-ia-api` | Define la URL |
| Branch | `main` | |
| Root Directory | **vacío** | Render no deja leer archivos fuera de esa carpeta, y el modelo está en `modelos/`, fuera de `backend/` |
| Language | Python 3 | |
| Build Command | `pip install uv==0.12.10 && cd backend && uv sync --frozen --extra llm` | Instala exactamente lo de `uv.lock` (`--frozen`), más `openai` para el chat |
| Start Command | `cd backend && uv run --frozen --no-sync uvicorn app.main:app --host 0.0.0.0 --port $PORT` | Render asigna el puerto en `$PORT`; `0.0.0.0` acepta conexiones de fuera |
| Instance Type | Free | |
| Health Check Path | `/api/v1/health` | Render solo da por bueno un despliegue que responde aquí |

**Variables de entorno:**

| Variable | Valor | Secreta |
|---|---|---|
| `PYTHON_VERSION` | `3.12.4` | no |
| `CORS_ORIGINS` | `https://<proyecto>.vercel.app,http://localhost:4200` (sin barra final) | no |
| `ENTORNO` | `produccion` | no |
| `OPENAI_API_KEY` | la clave del proyecto de OpenAI | **sí** |
| `OPENAI_ESFUERZO` | `minimal` (elegido con `scripts/evaluar_chat.py`) | no |
| `CHAT_PRESUPUESTO_DIARIO_USD` | `1.0` (tope de gasto del chat por día) | no |

No hace falta `RUTA_MODELO`: `config.py` calcula la raíz del repo y encuentra
`modelos/colono.joblib`.

**Plan gratuito.** El servicio se duerme tras 15 min sin tráfico y tarda cerca de un
minuto en despertar. El frontend lo avisa ("Despertando el servidor"). **Antes de
una demo, abre el enlace un par de minutos antes.**

## Vercel (frontend)

| Campo | Valor |
|---|---|
| Project Name | `colono-ia` |
| Framework Preset | Angular |
| Root Directory | `frontend` |
| Build y Output | los fija `frontend/vercel.json` (`npm run build` → `dist/colono-ia/browser`) |
| Variables de entorno | ninguna |

La URL del backend no es secreta: va compilada en
`frontend/src/environments/environment.ts`. En **Settings → Deployment Protection**,
la producción no debe pedir inicio de sesión.

Las vistas previas de Vercel (otras ramas) tienen URLs distintas y CORS las bloquea.
Es intencional.

## Orden la primera vez

1. Commit y push del código.
2. Crear el servicio en Render y anotar su URL.
3. Poner esa URL en `environment.ts`, y hacer commit y push.
4. Crear el proyecto en Vercel y anotar su URL.
5. Agregar la URL de Vercel a `CORS_ORIGINS` en Render.

## Comprobación

1. `https://<servicio>.onrender.com/api/v1/health` responde `"estado":"ok"` y
   `"modelo_cargado":true`.
2. El enlace de Vercel muestra "Servidor listo" y dibuja el tablero de demostración.
   En F12 no hay errores de CORS.
3. El enlace funciona desde un celular con datos móviles, fuera de la red de casa.

## Si algo falla

| Síntoma | Causa probable |
|---|---|
| `/health` dice `"modelo_cargado": false` | El modelo no está en el repo, o se fijó un Root Directory en Render |
| Error de CORS en la consola del navegador | La URL de Vercel en `CORS_ORIGINS` no coincide exactamente (`https`, sin barra final) |
| "Sin conexión" en la cabecera | `environment.ts` apunta a otra URL, o el servicio de Render falló al arrancar (revisar sus logs) |
| El build de Render muere sin mensaje | Memoria: el plan gratuito da 512 MB |
| El chat responde siempre igual y `/health` dice `chat_con_llm: false` | Falta `OPENAI_API_KEY`, o se agotó el presupuesto del día. Los logs de Render tienen una línea JSON por pregunta con el `motivo` |
| Muchas preguntas seguidas dan "espera unos minutos" | Límite por IP (`CHAT_PREGUNTAS_POR_IP` cada `CHAT_VENTANA_S` segundos) |
