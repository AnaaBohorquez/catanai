# AGENTS.md — Colono IA

Documento vivo. Se actualiza cuando se toma una decisión, se cambia una convención
o se descubre una trampa.

---

## 1. Qué es esto

Guía de Catan en dos fases. **Colocación inicial:** el usuario fotografía el tablero
recién armado y la app calcula, con el modelo, qué pareja de poblados conviene y
explica por qué. **Partida en curso:** el usuario sigue marcando sus poblados, sus
ciudades y los de los rivales, y un chat experto aconseja qué construir y hacia dónde
crecer, con reglas verificadas del juego.

Monorepo con `backend/` (FastAPI) y `frontend/` (Angular) al mismo nivel.

- **Usuario final:** jugador casual o intermedio que quiere mejorar.
- **Alcance:** Catan base, 3 o 4 jugadores. La colocación inicial con el modelo, y
  después la partida en curso como guía: el usuario sigue marcando sus poblados, sus
  ciudades y los de los rivales, y el chat aconseja qué construir y hacia dónde crecer.
- **Contexto:** trabajo final del Módulo 5. Demos el 1 y 3 de octubre de 2026.

**Flujo del usuario (sin login):**
1. Foto del tablero vacío, o el **tablero de demostración** (entra directo al paso 2 y
   sirve para la demo pública y las pruebas; la foto no debe bloquearla).
2. Revisar y corregir terrenos, números y puertos.
3. Marcar con clic los poblados de los rivales.
4. Pedir la recomendación (pareja inicial) y preguntar al chat por qué y cómo jugarla.
5. Marcar tus dos poblados: termina la colocación inicial y empieza la partida.
6. En partida, seguir marcando poblados, ciudades y rivales, y preguntar al chat
   «¿Qué construyo ahora?» o «¿Hacia dónde crezco?» (marca los destinos A, B y C).

«Nueva partida» vuelve al paso 3 con el mismo tablero o al paso 1.

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
| **Partida en curso: poblados, ciudades y rivales de un solo tipo** | Con dos piezas propias termina la colocación inicial (`PIEZAS_INICIALES`). Después no hay tope de 2: 5 poblados y 4 ciudades (juego base). La ciudad sale de tocar un poblado propio en modo Ciudad y cuenta doble. Los rivales no se distinguen por color: basta para la regla de distancia y para ver quién compite cerca. Los caminos no se marcan |
| **Tercer poblado por fórmula a la vista, no por la regresión** | El modelo se entrenó para elegir la pareja inicial. `domain/expansion.py` puntúa pips + 0.5 × pips de recursos nuevos + puerto − caminos extra − rival cerca, con pesos a criterio. Sin marcar caminos: la distancia se cuenta desde los poblados y un camino no cruza un poblado rival |
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

### 5.15 Una clave rechazada dejaba el chat en modo básico sin avisar
Con una clave revocada, OpenAI responde `AuthenticationError`, el chat cae a
plantillas y `/health` seguía diciendo `chat_con_llm: true` (solo miraba si había
clave). Parecía que "el chat responde mal". Ahora `consumo.clave` recuerda el rechazo
10 minutos (no se reintenta en cada pregunta), `/health` da `chat_motivo`
(`sin_clave`, `clave_invalida`, `sin_presupuesto`) y el frontend muestra «⚙️ Modo
básico». Las plantillas normalizan la pregunta (sin acentos ni signos) y reconocen
estrategia, costos, probabilidades y reglas.


### 5.16 El tamaño de las fichas cambia con cada foto
Con un solo rango de radios, Hough encontraba primero círculos falsos grandes (sobre
la arena o los campos), tomaba su radio como el típico y descartaba las fichas
reales: 0 fichas y ningún número en `logs/ejemplo-catan-2.png`. Ahora se prueban
tres bandas de radio (`BANDAS_DE_RADIO`) y se queda la red que explica más fichas;
un círculo solo cuenta si tiene tinta en el centro.

### 5.17 La arena del desierto está saturada; el 2 casi no tiene tinta
El rango de color del desierto (s < 80) no coincidía con la arena real (s ≈ 130–150)
y el desierto se buscaba solo por "menos tinta": un 2, de trazo fino, ganaba. Ahora
se combinan tinta y color típico (`_arena`, por mediana).

### 5.18 Las fichas volteadas cambian las pistas del 6/8 y de los pips
La abertura del 6 y la franja de los pips suponen la ficha derecha. Cada ficha se
endereza con la dirección número→pips (`orientacion_de_ficha`), pero esa medida es
ruidosa con pips de 1–2 px: se usa el giro del grupo mayor de fichas y solo las que
se apartan más de 40° usan el suyo (`giros_de_fichas`).

### 5.19 Una etiqueta asignada por descarte no es una lectura
La asignación con reparto (`asignar_con_reparto`, algoritmo húngaro) mide la
seguridad de cada ficha como cuánto empeora el total si se le prohíbe su etiqueta.
Pero si la ficha misma se leía como otra cosa (un 6 que recibe el 8 "sobrante"), esa
seguridad engaña: se fuerza a 0 y queda para revisión.

### 5.20 Con los dos poblados puestos, el chat creía estar en la primera colocación
`mio` solo se llena con exactamente un poblado propio, así que con dos el frontend no
mandaba ninguno: el estado decía "primera colocación" y las herramientas pedían una
recomendación que ya no se podía pedir. Ahora `PeticionChat.propios` lleva todos, el
estado dice "colocación inicial completa" y las herramientas de opciones redirigen a
`hacia_donde_expandir`.

### 5.21 Las rondas de la partida usan la misma fórmula que las variables
`turnos_hasta()` (en `variables.py`) salió de `variables_de_pareja` para reutilizarla
con todas las piezas del usuario (`domain/partida.py`). Se comprobó que las variables
de 100 parejas quedan idénticas: el modelo no cambia. Si se toca esa función, cambian
a la vez el dataset y los consejos de partida.
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
- **Las marcas del tablero son la única verdad de la partida.** `marcas` en `App`
  (vértice → `propio`, `ciudad` o `rival`); la lógica de cada toque está en
  `tocar()` de `colocacion.ts`. Con dos piezas propias (`PIEZAS_INICIALES`) termina
  la colocación inicial: «Recomendar» se apaga y el chat recibe `propios` y
  `ciudades` para aconsejar la partida. De ellas salen `mio` y `ocupados` para
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
- **Las respuestas del chat tienen formato de tarjeta.** Un Markdown mínimo (`### título`,
  `**Subtítulo**` en su línea, listas `- ` y `1. `, `Haz:`/`Evita:`) que
  `asistente/formato.ts` convierte en bloques y Angular dibuja como las tarjetas. Nunca
  se inserta HTML: lo que escriba el LLM no puede meter etiquetas en la página. El LLM
  lo pide `INSTRUCCIONES` y las plantillas lo producen igual; `sin_estado()` quita el
  eco de la línea "[Estado: …]".
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
| Visión: terreno por color | red ajustada con las fichas (3 bandas de tamaño) + anillo de color, repartido 4-4-4-3-3 con el algoritmo húngaro; el desierto por tinta y color de arena. **19/19** en las dos fotos de ejemplo, también giradas 90°, 180°, 25° y −40°. Rangos de color **sin calibrar con fotos de celular** |
| Visión: lectura de números | fichas enderezadas por sus pips; rojo + dígitos + agujeros + abertura del 6/8 + pips, sobre 7 recortes; reparto con el algoritmo húngaro. Referencia: **18/18** en todos los giros y **0 errores con confianza alta**; ~10 quedan para revisión (pips de 2 px). `ejemplo-catan-2.png` (fichas de 12 px, tablero no estándar: desierto con 10 y tres 9): 7–11 de 19. Sin probar con fotos de celular |
| Visión: puertos | plantilla del marco, editable en la revisión |
| Revisión del tablero | lista: empieza en el primer dudoso; opciones más probables de un toque; al corregir, `reacomodar()` mueve sola la ficha con la que se confundió y lo avisa; «Todo se ve bien» acepta lo dudoso; contador contra el reparto; girar/mover/cambiar puertos; confirmar con `/tableros/validar` |
| Foto | subir o tomar con la cámara del celular (`capture`); se reduce a 1600 px en el navegador y no se guarda en el backend |
| Chat: plantillas y LLM | LLM con herramientas, verificador, límites y registro; probado en vivo con `gpt-5-mini` (≈ US$0.001 por pregunta, 7 s). Clave rechazada detectada y avisada (§5.15). Plantillas normalizadas con intención de estrategia. Falta correr `scripts/evaluar_chat.py` con las 5 preguntas de estrategia |
| Reglas verificadas | borrador de 17 entradas en `domain/reglas.md`, **ninguna verificada**: hasta entonces el chat no cita reglas. Ana las revisa en la página «Reglas de Catan por verificar» y `scripts/aplicar_verificacion.py` pasa sus resultados a `reglas.md`. `test_la_regla_de_costos_coincide_con_la_tabla_del_codigo` mantiene la de costos igual a `COSTOS` |
| Marcar la colocación y la partida | modo + toque (Mi poblado, Ciudad, Rival, Borrar); regla de distancia en el cliente; recálculo automático; segunda colocación con `mio`. En partida: hasta 5 poblados y 4 ciudades; «🧭 ¿Hacia dónde crezco?» (`/expansion` y `hacia_donde_expandir`) marca los destinos A, B y C con su ruta. Los caminos no se marcan |
| Guía de la partida | `domain/partida.py`: producción de todas tus piezas (ciudades ×2), números que te pagan, puertos y rondas hasta cada construcción con la misma fórmula que el modelo (`turnos_hasta`). Herramienta `mi_produccion`; `plan_de_construccion`, `como_conseguir` y `que_me_falta` usan tus piezas reales en partida. Modo básico con plantilla «Tu partida» |
| Herramientas del asistente | 14 (con `mi_produccion` y `hacia_donde_expandir`); antes 12: 5 sobre las opciones, el tablero marcado y las reglas; 6 de experto (costos, mano, conseguir un recurso, plan de construcción, probabilidades, tablero) y `explicar_estrategia` (ficha de la familia, perfil frente al centro de su grupo en KMeans, plan ordenado por la prioridad de la familia). Todas calculadas desde el dominio o el modelo |
| Plantilla "22 % más de puntos" | cifra retirada del chat hasta verificarla contra `parejas.csv` (`make dataset`) |
| Frontend Angular | diseño "tablero + asistente": tablero fijo con la opción resaltada; panel con franja de opciones, tarjetas dentro del chat y campo fijo en móvil. Un solo estado de selección en `App`. Botón «¿Cómo juego esta estrategia?» en cada tarjeta y «Nueva partida» (nueva colocación en el mismo tablero o empezar de cero) |
| Despliegue | configuración lista (`docs/despliegue.md`); falta crear los servicios |
