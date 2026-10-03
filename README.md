# Colono IA

Tu guía para colocar y jugar Catan. Fotografía el tablero recién armado: la app te
dice dónde poner tus dos primeros poblados y por qué. Después sigue contigo durante
la partida: marcas lo que pasa en la mesa y un asistente experto te aconseja qué
construir y hacia dónde crecer.

Trabajo final del Módulo 5 del diplomado. Ana Bohórquez, 2026.

## El problema

La colocación inicial decide buena parte de la partida y se toma por intuición en
menos de un minuto. Sobre 200 tableros simulados, la pareja que recomienda el modelo
vale **un punto de victoria más** que la que elegiría un jugador guiándose por los
pips, que es el criterio habitual en la mesa. Y una vez colocados los poblados, el
jugador casual sigue sin saber qué construir primero ni hacia dónde expandirse.

## Qué hace

**1. Leer el tablero.** Desde una foto (subida o tomada con la cámara del celular) o
con el tablero de demostración. La visión lee terrenos y números a partir de las
fichas, aunque la foto esté girada; los puertos salen de la plantilla del marco. En la
revisión, lo dudoso se corrige con un toque y la app reacomoda sola el resto para que
cuadre el reparto del juego base.

**2. Recomendar la colocación inicial.** Una regresión lineal entrenada con partidas
simuladas puntúa cada pareja de vértices legal. Muestra tres opciones de estrategias
distintas (🛤️ Expansión, 🏰 Ciudades y desarrollo, ⚓ Puerto y conversión), resaltadas
en el tablero, con su explicación. Marcas los poblados de los rivales con un clic y
las opciones se recalculan; con tu primer poblado puesto, recomienda el segundo.

**3. Guiar la partida.** Al poner tus dos poblados empieza la partida. Sigues marcando
tus poblados, tus ciudades (🏰) y los de los rivales, y el asistente:
- calcula tu producción real (las ciudades cuentan doble), qué números te pagan y en
  cuántas rondas puedes construir cada pieza;
- marca en el tablero hacia dónde crecer: los destinos A, B y C para tu siguiente
  poblado, con la ruta de caminos.

**4. Conversar con un experto.** Un chat con GPT-5 mini que no inventa: consulta
herramientas del backend (el modelo, el tablero, la producción, reglas verificadas) y
un verificador rechaza cifras que no salgan de ellas. Responde con el formato de las
tarjetas y, sin clave o sin presupuesto, cae a un modo básico con plantillas.

## Arquitectura

```
├── backend/          FastAPI · dominio, modelo, visión, chat, partida
├── frontend/         Angular · interfaz
├── notebooks/        EDA y modelado, reproducibles en Colab
├── modelos/          colono.joblib, generado por el notebook 02
├── data/processed/   parejas.csv, generado por scripts/generar_dataset.py
└── docs/             conceptos del juego, decisiones y despliegue
```

## Arranque rápido

```bash
make setup          # instala backend y frontend
make dev-backend    # API en http://localhost:8000/docs
make dev-frontend   # interfaz en http://localhost:4200
```

En Windows con PowerShell (sin `make`), ver la sección 2 de `AGENTS.md`. Para el chat
con LLM, pon `OPENAI_API_KEY` en `backend/.env` (nunca en el código ni en el frontend).

## La API

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/health` | Estado del servicio y del chat |
| GET | `/api/v1/modelo` | Variables y métricas del modelo |
| GET | `/api/v1/tableros/aleatorio` | Un tablero válido para probar |
| POST | `/api/v1/tableros/validar` | Revisa un tablero contra el reparto del juego base |
| POST | `/api/v1/vision/tablero` | Lee el tablero de una foto |
| POST | `/api/v1/recomendar` | **La colocación inicial**: mejores parejas de poblados |
| POST | `/api/v1/expansion` | Hacia dónde crecer: destinos para el siguiente poblado |
| POST | `/api/v1/chat` | El asistente: colocación, partida y reglas |

Documentación interactiva en `/docs`.

## Regenerar datos y modelo

```bash
make dataset                      # ~25 min, 200 tableros
jupyter notebook notebooks/       # 01_eda.ipynb y luego 02_modelo.ipynb
```

## Documentación

- `AGENTS.md`: reglas de trabajo, decisiones, trampas encontradas y estado
- `docs/conceptos-catan.md`: el dominio del juego y cada pieza de la app explicados
- `docs/despliegue.md`: Render (backend) y Vercel (frontend)
- `backend/app/domain/reglas.md`: las reglas que puede citar el asistente
