# AGENTS.md — Colono IA

Documento vivo. Se actualiza cuando se toma una decisión, se cambia una convención
o se descubre una trampa.

---

## 1. Qué es esto

Recomendador de colocación inicial en Catan. El usuario fotografía el tablero recién
armado, la app calcula qué pareja de poblados conviene y explica por qué.

Monorepo con `backend/` (FastAPI) y `frontend/` (Angular) al mismo nivel.

- **Usuario final:** jugador casual o intermedio que quiere mejorar.
- **Alcance:** Catan base, 3 o 4 jugadores, solo la fase de colocación inicial.
- **Contexto:** trabajo final del Módulo 5. Demos el 1 y 3 de octubre de 2026.

**Flujo del usuario (sin login):** ① foto del tablero vacío → ② revisar y corregir
terrenos, números y puertos → ③ marcar con clic los poblados ajenos → ④ pedir la
recomendación y preguntar al chat. El **tablero de demostración** entra al mismo
flujo en ② y sirve para la demo pública y las pruebas; la foto no debe bloquearla.

Lee `docs/conceptos-catan.md` antes de tocar nada del dominio.

---

## 2. Comandos

```bash
make help              # lista todo
make setup             # instala backend y frontend
make dev-backend       # API en :8000, documentación en /docs
make dev-frontend      # interfaz en :4200
make test              # pruebas del backend
make lint              # estilo
make dataset           # regenera data/processed/parejas.csv (~25 min)
make openapi           # exporta el contrato a openapi.json
make up / make down    # todo en contenedores
```

**En Windows con PowerShell** (sin WSL; el `Makefile` usa Bash). Desde la raíz:

```powershell
cd backend;  uv run uvicorn app.main:app --reload --port 8000   # API
cd backend;  uv run pytest -q                                   # pruebas backend
cd backend;  uv run python -m scripts.exportar_openapi          # escribe ..\openapi.json
cd frontend; npm run api:tipos      # regenera src\app\api\esquema.d.ts desde openapi.json
cd frontend; npm start              # interfaz en :4200
cd frontend; npx ng test --watch=false
```

Tras cambiar un esquema del backend: exportar el OpenAPI y luego `npm run api:tipos`.
`esquema.d.ts` sí se versiona (Vercel compila sin backend); `openapi.json` no.
Un `npm start` que ya corría **no** relee `angular.json`: si cambia, reinícialo.

---

## 3. Stack verificado

| Capa | Herramienta |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic v2, uvicorn |
| Visión | OpenCV headless |
| Modelo | scikit-learn **1.8.0 fijo** (regresión lineal + KMeans), joblib |
| Frontend | Angular 22+, Tailwind |
| Asistente | OpenAI `gpt-5-mini` por la Responses API, con herramientas propias. Paquete `openai` en el extra `llm` |
| Contenedores | Docker + docker compose (solo local; no se usa para desplegar) |
| Despliegue | Backend en Render (Python nativo + uv), frontend en Vercel. Detalle en `docs/despliegue.md` |

---

## 4. Decisiones cerradas — no reabrir sin avisar

| Decisión | Motivo |
|---|---|
| **Regresión lineal, no ensambles** | 12 variables dan R² 0.633; las 40 dan 0.656. Veintitrés milésimas no valen perder la interpretación, y los coeficientes SON la explicación que ve el usuario |
| **Objetivo: puntos simulados, no producción de recursos** | La producción esperada se calcula con una fórmula exacta (pips/36). El modelo habría sacado R² de 1 sin aprender nada |
| **Se modelan PAREJAS de vértices, no vértices sueltos** | En Catan se colocan dos poblados. Un vértice suelto tiene madera y ladrillo a la vez solo en el 9% de los casos; una pareja, en el 48% |
| **Datos por simulación propia** | Aprobado explícitamente por el profesor. No existe API pública de partidas de Catan |
| **La foto solo lee el tablero VACÍO** | Detectar poblados ajenos es mucho más difícil (piezas de 1 cm, ocluidas, en cuatro colores) y un fallo invalidaría la recomendación. Los poblados ajenos se marcan con clic, que además es más rápido para quien está sentado en la mesa |
| **Sin login ni panel de administrador** | El profesor declaró el login opcional el 12 de septiembre. Para este producto no hay datos multiusuario que administrar |
| **Puertos de un tablero de foto: plantilla editable** | La foto no lee puertos. La plantilla (`domain/puertos.py`) reproduce el tablero de principiantes, medido sobre `logs/ejemplo-tablero.png`: aristas de costa 2, 5, 9, 12, 15, 19, 22, 25 y 29. Madera, oveja y mineral están **por confirmar** (`POR_CONFIRMAR`). El usuario gira, mueve y cambia tipos al revisar |
| **Render con Python nativo + uv, no Docker** | Sin Docker en la máquina de desarrollo, la imagen solo se probaría en Render, con un ciclo de commit y build por cada fallo. Render corre los mismos comandos `uv` que se usan en local |
| **Chat con LLM y herramientas** | El profesor ve un chat que entiende preguntas libres. El LLM no recibe datos en el prompt: los pide a herramientas del backend, y un verificador rechaza cifras que no salgan de ellas. Sin clave, sin presupuesto o si algo falla, responde con plantillas |
| **Las alternativas no incluyen la familia desequilibrada** | Su consejo es "cambia de pareja". Antes aparecía como opción 2 o 3 en 6 de 30 tableros. `SOLO_SI_ES_LA_MEJOR` en `recomendador.py` solo la deja entrar como opción 1. Diversificar cuesta en promedio 0.74 puntos estimados en la opción 2 y 1.84 en la 3, y la UI lo dice |

**Descartado y no reintroducir:** reinforcement learning, simulación de partidas
completas con catanatron, CNN para clasificar piezas, probabilidad de victoria como
objetivo, LightGBM o XGBoost, Streamlit como frontend final.

---

## 5. Trampas verificadas

### 5.1 La producción se cobra en TODAS las tiradas, no solo en la propia
Primera versión del simulador: cada pareja sacaba 1.2 puntos y no se distinguía nada.
En Catan cobras cuando sale tu número aunque tire otro jugador. Con 4 jugadores son
4 tiradas por ronda. Por eso `jugar_ronda()` recibe `jugadores`.

### 5.2 Una variable constante dentro del tablero no sirve para nada
La app ordena las parejas de UN tablero. Cualquier cantidad igual para todas ellas
(el total de pips del tablero, su promedio) no puede explicar por qué una es mejor.
`verificar_variabilidad()` lo caza automáticamente. Ya eliminó `par_poblado`
(siempre 0 en vértices sueltos), `espacio_ruta_larga` (siempre 6) y
`pips_relativos` (la misma columna reescalada).

### 5.3 Los turnos hasta construir deben contemplar el comercio
Sin contarlo, un recurso que no produces daba "nunca construyes" y la variable
topaba en 60 para casi todas las parejas. Con el cambio 4:1 del banco la media de
`turnos_a_camino` pasó de 55 a 9.8.

### 5.4 Elegir candidatos por pips excluye todos los puertos
Los puertos están en la costa, y los vértices costeros tocan menos hexágonos, así
que nunca entran por pips. `puerto_alineado` salía constante en cero. Por eso
`parejas_candidatas()` añade los mejores vértices con puerto aparte del top por pips.

### 5.5 La correlación del puerto engaña; hay que mirar el coeficiente
`puerto_alineado` correlaciona −0.035 con los puntos, pero su coeficiente en la
regresión es **positivo**. La correlación mezcla "tiene puerto" con "está en la
costa y produce menos". La regresión los separa al controlar por producción.

### 5.6 La partición va por tablero, nunca por fila
Las ~193 parejas de un tablero comparten los mismos hexágonos. Usar
`GroupShuffleSplit` sobre `tablero_id`.

### 5.7 `control_<recurso>` puede pasar de 1
Si los dos poblados tocan el mismo hexágono se cobra doble, así que se recibe más
de lo que el tablero contiene contando una sola vez. La cota es 2, no 1.

### 5.8 Streamlit exige `key` en widgets repetidos
El identificador se genera del tipo y los parámetros. Dos gráficas iguales en
pestañas distintas chocan. (Histórico: el frontend ya no es Streamlit.)

### 5.9 Números que deben cuadrar siempre
19 hexágonos, 54 vértices, 72 aristas, 18 fichas numéricas, 9 puertos, 58 pips.
Si alguno falla, algo se rompió.

### 5.10 El `.joblib` exige la versión de scikit-learn con la que se entrenó
El modelo se entrenó con 1.8.0 y `uv.lock` había subido a 1.9.1: cargaba, pero con
`InconsistentVersionWarning`, que avisa que los resultados pueden cambiar. Por eso
`scikit-learn==1.8.0` va fijo en `pyproject.toml`. Se comprobó que con 1.8.0 las
predicciones de 3 tableros coinciden exactamente. Si se reentrena con otra versión,
cambiar el pin en el mismo commit.

### 5.11 Render no ve archivos fuera de su Root Directory
`modelos/` está fuera de `backend/`. Por eso el servicio de Render no fija Root
Directory y sus comandos empiezan con `cd backend`. Con eso, `RAIZ` de `config.py`
encuentra `modelos/colono.joblib` sin variables extra.


### 5.12 La cuadrícula de la foto se ajusta con las fichas, no con el borde
El método del borde suponía una separación entre filas que no era la real y
muestreaba sobre bordes y mar: 10/19 terrenos. Las fichas numéricas marcan el centro
exacto de cada hexágono; con unas pocas se ajusta la red y una homografía. Dos
detalles que costaron: el vector base sale de una pareja al azar y hay que girarlo
hasta que apunte a la derecha (si no, la lectura sale rotada), y el ajuste final va
con RANSAC estricto (un solo falso positivo promediado movía los centros 12 px).

### 5.13 En fichas pequeñas, una sola pista no basta para un número seguro
Con umbral fijo el desenfoque rellena los agujeros del 6 y del 8 (se usa Otsu por
ficha), y la compresión JPEG los vuelve a mover. Por eso: el 6 y el 8 llevan una
segunda pista independiente (la abertura arriba a la derecha), cada ficha se relee
con 7 recortes y solo es segura si la lectura no cambia, y la confianza se mide contra
TODOS los números, no solo los que quedan en el reparto. Si no, una ficha asignada
"por descarte" parecía una lectura segura.

### 5.14 `cv2.imread` no abre rutas con acentos en Windows
La ruta del proyecto tiene "Actuaría". Leer bytes y usar `cv2.imdecode`.
---

## 6. Arquitectura

- **Monorepo**, backend y frontend al mismo nivel. No microservicios.
- **El frontend nunca redefine los tipos del backend.** Se generan desde el
  OpenAPI con `make openapi`.
- **La API va versionada** en `/api/v1`.
- **El dominio no sabe que existe la web.** `app/domain/` es Python puro y se puede
  usar desde los notebooks; `app/services/` orquesta; `app/api/` solo traduce.
- **Los vértices viajan como texto**, no como conjuntos. `app/services/serializers.py`
  traduce en ambos sentidos.
- **El backend arranca aunque el modelo falte.** `/health` responde `degradado` en
  vez de no levantar el servicio.
- **El chat no calcula ni inventa.** Toda cifra de una respuesta sale de una
  herramienta (`services/herramientas.py`), y `cifras_sin_respaldo()` lo verifica.
  Puede **pedir** una recomendación nueva al recomendador (`solicitar_recomendacion`,
  el mismo cálculo que `/recomendar` en `services/recomendacion.py`), nunca
  redactarla. Los consejos que no salen de herramientas van etiquetados como
  "Consejo general". Sin clave de LLM cae a plantillas.
- **Las reglas del juego salen de `domain/reglas.md`**, y solo las entradas con
  `verificado: sí`. El archivo se lee una vez por proceso: tras editarlo, reiniciar
  el backend.
- **Las marcas del tablero son la única verdad de la colocación en curso.** `marcas`
  en `App` (vértice → propio o rival). De ellas salen `mio` y `ocupados` para
  `/recomendar` y para el chat, y los bloqueados por la regla de distancia
  (`sonVecinos()` en `tablero/geometria.ts`: dos vértices son vecinos si comparten
  dos hexágonos, igual que en el dominio). Tras el primer "Recomendar", cambiar
  marcas o jugadores recalcula solo.
- **En el chat los vértices se nombran como en pantalla: "opción N, poblado K".** El
  modelo de lenguaje nunca ve ni escribe ids; `solicitar_recomendacion` los resuelve
  y devuelve `estado_nuevo` para que el tablero marque la hipótesis.
- **Las pruebas nunca usan la clave real.** `tests/conftest.py` la vacía en cada
  prueba; las del LLM usan un cliente simulado. Sin esto, con la clave en `.env`,
  `pytest` llamaba a OpenAI y gastaba saldo.
- **El chat público tiene límites** (`services/consumo.py`): preguntas por IP, un
  presupuesto diario en US$ y una línea JSON por pregunta con tokens, latencia y
  costo.
- **El chat habla de la opción que el usuario eligió.** `PeticionChat.elegida` (índice
  desde 0) dice cuál; el frontend manda también el tablero y las opciones ya
  calculadas. Toda cifra de una respuesta sale de esas opciones.

---

## 7. Convenciones

### Backend
- Nombres en español, sin acentos ni eñes en identificadores: `pips_del_vertice`,
  `montanas`, `produccion_esperada`.
- Docstrings en formato NumPy. Los comentarios explican **por qué**, no qué.
- Cualquier proceso aleatorio acepta `semilla`.
- Las funciones de verificación se llaman `verificar_*` y lanzan `AssertionError`.
- Sin dependencias nuevas sin justificarlo.

### Git
- Commits manuales. **Nunca commit ni push automático.**
- Mensajes en español, en imperativo.

### Trabajo con agentes
- **Siempre empezar en modo plan.** Proponer, esperar aprobación, después escribir.
- Cambios pequeños y verificables, corriendo el código después de cada uno.
- Si una librería cambió, verificar la documentación oficial en vez de asumir.
- **Nada entra al proyecto que Ana no pueda explicar sola en el Q&A.** Si un bloque
  necesita un concepto que no está en `docs/conceptos-catan.md`, documentarlo ahí en
  el mismo cambio.

---

## 8. Estado

| Pieza | Estado |
|---|---|
| Dominio: tablero, variables, simulador | listo |
| Dataset: 200 tableros, ~39 000 parejas | listo |
| Notebooks de EDA y modelado | listos |
| Backend: API, esquemas, tests | listo y probado en local |
| Dockerfile | desactualizado: no copia `modelos/` (el despliegue no lo usa) |
| Visión: terreno por color | red ajustada con las fichas + anillo de color; el desierto es el hexágono sin tinta. Foto de referencia (539 px): **19/19**, también recomprimida en JPEG 70–95. Rangos de color **sin calibrar con fotos de celular** |
| Visión: lectura de números | rojo + dígitos + agujeros + abertura del 6/8 + pips, promediados sobre 7 recortes, asignados respetando el reparto. Referencia: **18/18** (también en JPEG 70–95) y **0 errores con confianza alta**; 12–13 quedan marcados para revisión por la baja resolución. Sin probar con fotos de celular |
| Visión: puertos | plantilla del marco, editable en la revisión |
| Revisión del tablero | lista: corregir terreno y número por hexágono, contador contra el reparto, girar/mover/cambiar puertos, confirmar con `/tableros/validar` (que ahora también revisa el reparto de terrenos y de fichas) |
| Foto | subir o tomar con la cámara del celular (`capture`); se reduce a 1600 px en el navegador y no se guarda en el backend |
| Chat: plantillas y LLM | LLM con herramientas, verificador, límites y registro listos y probados con un cliente simulado. Falta la clave para probarlo en vivo y correr `scripts/evaluar_chat.py` |
| Reglas verificadas | borrador de 17 entradas en `domain/reglas.md`, **ninguna verificada**: hasta entonces el chat no cita reglas. `test_la_regla_de_costos_coincide_con_la_tabla_del_codigo` mantiene la de costos igual a `COSTOS` |
| Marcar la colocación | modo + toque (Mi poblado, Rival, Borrar); regla de distancia en el cliente; recálculo automático; segunda colocación con `mio`. Los caminos no cuentan todavía |
| Herramientas del asistente | 11 (con `ver_estado_del_tablero`); antes 10: 4 sobre las opciones y reglas, y 6 de experto (costos, mano, conseguir un recurso, plan de construcción, probabilidades, tablero), todas calculadas desde el dominio |
| Plantilla "22 % más de puntos" | cifra retirada del chat hasta verificarla contra `parejas.csv` (`make dataset`) |
| Frontend Angular | diseño "tablero + asistente": tablero fijo con la opción resaltada; panel con franja de opciones, tarjetas dentro del chat y campo fijo en móvil. Un solo estado de selección en `App` |
| Despliegue | configuración lista (`docs/despliegue.md`); falta crear los servicios |
