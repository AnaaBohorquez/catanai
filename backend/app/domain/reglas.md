# Reglas de Catan (juego base) para el asistente

Este archivo es la **única fuente de reglas** del chat: la herramienta
`consultar_reglas` busca aquí y **solo devuelve las entradas con `verificado: sí`**.

Cómo verificar una entrada:

1. Compara el texto con el reglamento oficial del juego base.
2. Completa `fuente:` con la sección y la página (por ejemplo, "Reglamento, p. 7").
3. Corrige lo que no coincida y cambia `verificado: no` por `verificado: sí`.

Formato: cada entrada empieza con `## id`; las tres líneas siguientes son
`temas:`, `fuente:` y `verificado:`; el resto, hasta la siguiente entrada, es el
texto que verá el asistente.

---

## colocacion-inicial
temas: colocación inicial, fundación, empezar, primer poblado, segundo poblado, serpiente, orden
fuente: Reglamento del juego base — preparación / fase de fundación (completar página)
verificado: no

Cada jugador coloca un poblado y un camino pegado a él, en orden de turno. Después,
en orden inverso (el último en colocar es el primero en la segunda vuelta), cada
jugador coloca su segundo poblado y su segundo camino. Por eso se le llama orden
"en serpiente": el último jugador coloca sus dos poblados seguidos.

## regla-de-distancia
temas: distancia, vértice, esquina, cerca, vecino, junto, poblado
fuente: Reglamento del juego base — construir un poblado (completar página)
verificado: no

Un poblado solo puede ir en un vértice cuyas tres esquinas vecinas estén libres: entre
dos poblados o ciudades siempre tiene que haber al menos dos caminos de distancia.
Esta regla aplica también a la colocación inicial.

## recursos-segundo-poblado
temas: recursos iniciales, cartas iniciales, segundo poblado, empezar
fuente: Reglamento del juego base — fase de fundación (completar página)
verificado: no

Al colocar el segundo poblado de la fundación, cada jugador recibe una carta de
recurso por cada hexágono de terreno que toca ese poblado. El desierto no da nada. El
primer poblado no da cartas iniciales.

## produccion
temas: producción, tirada, dados, número, cobrar, recibir, cartas, ciudad
fuente: Reglamento del juego base — producción de recursos (completar página)
verificado: no

Al empezar su turno, el jugador tira dos dados. Todos los jugadores (no solo el que
tira) reciben recursos de los hexágonos con ese número: una carta por cada poblado y
dos por cada ciudad que toque el hexágono. El hexágono donde está el ladrón no
produce.

## siete-y-ladron
temas: siete, 7, ladrón, descartar, robar, bloquear, mitad
fuente: Reglamento del juego base — sale un 7 (completar página)
verificado: no

Cuando sale un 7 nadie produce. Todo jugador con más de 7 cartas en la mano descarta
la mitad, redondeando hacia abajo. Luego quien tiró mueve el ladrón a otro hexágono y
roba una carta al azar a un jugador con poblado o ciudad junto a ese hexágono.

## comercio
temas: comercio, cambiar, intercambio, banco, 4:1, 3:1, 2:1, puerto, comerciar
fuente: Reglamento del juego base — comercio (completar página)
verificado: no

En su turno, el jugador puede comerciar con los demás jugadores o con el banco. Con
el banco cambia 4 cartas iguales por 1 de su elección. Con un poblado o ciudad en un
puerto 3:1 cambia 3 iguales por 1; en un puerto 2:1 cambia 2 cartas del recurso de
ese puerto por 1 de su elección.

## costos
temas: costo, cuesta, precio, construir, camino, poblado, ciudad, carta de desarrollo, qué necesito
fuente: Reglamento del juego base — tabla de costos de construcción (completar página)
verificado: no

Camino: 1 madera y 1 ladrillo. Poblado: 1 madera, 1 ladrillo, 1 trigo y 1 oveja.
Ciudad: 2 trigo y 3 mineral (sustituye a un poblado propio). Carta de desarrollo:
1 mineral, 1 trigo y 1 oveja.

## puntos-de-victoria
temas: ganar, victoria, puntos, 10, fin de la partida, cuánto vale
fuente: Reglamento del juego base — fin de la partida (completar página)
verificado: no

Gana el primer jugador que llega a 10 puntos de victoria en su propio turno. Cada
poblado vale 1 punto y cada ciudad 2. El camino más largo y el ejército más grande
valen 2 puntos cada uno, y cada carta de punto de victoria vale 1.

## camino-mas-largo
temas: camino más largo, gran ruta comercial, ruta, caminos seguidos
fuente: Reglamento del juego base — camino más largo (completar página)
verificado: no

El primer jugador con una ruta continua de al menos 5 caminos recibe la carta de
camino más largo (2 puntos). Si otro jugador construye una ruta más larga, se la
quita. Un poblado ajeno construido en medio de una ruta la corta.

## ejercito-mas-grande
temas: ejército más grande, gran caballería, caballero, caballeros
fuente: Reglamento del juego base — ejército más grande (completar página)
verificado: no

El primer jugador que juega 3 cartas de caballero recibe la carta de ejército más
grande (2 puntos). Si otro jugador juega más caballeros que él, se la quita. Cada
caballero permite mover el ladrón y robar una carta.

## cartas-de-desarrollo
temas: carta de desarrollo, jugar carta, caballero, monopolio, invento, construcción de carreteras
fuente: Reglamento del juego base — cartas de desarrollo (completar página)
verificado: no

Solo se puede jugar una carta de desarrollo por turno, y no en el mismo turno en que
se compró. Las cartas de punto de victoria no se juegan: se revelan cuando dan la
victoria.

## limite-de-piezas
temas: piezas, cuántos poblados, cuántas ciudades, cuántos caminos, límite
fuente: Reglamento del juego base — componentes (completar página)
verificado: no

Cada jugador tiene 5 poblados, 4 ciudades y 15 caminos. Al subir un poblado a ciudad,
el poblado vuelve a la reserva del jugador y puede usarse de nuevo.

## orden-del-turno
temas: turno, orden del turno, qué hago en mi turno, fases
fuente: Reglamento del juego base — el turno (completar página)
verificado: no

En su turno, el jugador primero tira los dados para la producción. Después puede
comerciar (con otros jugadores o con el banco y los puertos) y construir, y al final
pasa los dados al siguiente jugador.

## comercio-entre-jugadores
temas: comercio entre jugadores, negociar, intercambiar con otros, ofrecer
fuente: Reglamento del juego base — comercio interior (completar página)
verificado: no

Durante su turno, el jugador activo puede cambiar cartas de recurso con los demás
jugadores en las proporciones que acuerden. Los demás jugadores solo pueden comerciar
con el jugador activo, no entre ellos.
PENDIENTE AL VERIFICAR: ¿permite tu edición regalar cartas? Añádelo aquí si aplica.

## mazo-de-desarrollo
temas: mazo, cartas de desarrollo, cuántas cartas, caballeros, composición
fuente: Reglamento del juego base — componentes (completar página)
verificado: no

El mazo de desarrollo tiene 25 cartas: 14 caballeros, 5 de punto de victoria y 6 de
progreso (2 de construcción de carreteras, 2 de invento y 2 de monopolio).

## cartas-de-progreso
temas: progreso, monopolio, invento, descubrimiento, construcción de carreteras
fuente: Reglamento del juego base — cartas de progreso (completar página)
verificado: no

Construcción de carreteras: colocas 2 caminos gratis. Invento: tomas 2 cartas de
recurso cualesquiera del banco. Monopolio: nombras un recurso y todos los demás
jugadores te dan todas sus cartas de ese recurso.

## ladron-al-inicio
temas: ladrón al inicio, dónde empieza el ladrón, desierto
fuente: Reglamento del juego base — preparación (completar página)
verificado: no

Al empezar la partida, el ladrón se coloca en el desierto. El desierto no tiene ficha
numérica y nunca produce.
