# Guion de avances — Colono IA

Para presentarle al profesor. Unos 5 minutos hablando, más la demostración.
Las indicaciones entre corchetes son para ti, no se leen.

---

## 1 · El problema (30 segundos)

> Mi proyecto es sobre Catan, y en concreto sobre el momento en que se decide la partida
> sin que nadie se dé cuenta: la colocación inicial.
>
> Antes de tirar el primer dado eliges dónde van tus dos poblados. Esa decisión la toma
> todo el mundo por intuición, en menos de un minuto, y condiciona el resto del juego.
>
> Medí qué tanto importa. Generé 300 tableros aleatorios y comparé los 54 vértices de cada
> uno. **El mejor vértice de un tablero produce casi el doble que un vértice promedio.**
> Ese hueco es el que nadie está aprovechando.

---

## 2 · La empresa y el usuario (30 segundos)

> La empresa se llama Colono IA. El usuario es el jugador casual o intermedio que quiere
> mejorar y no sabe por dónde empezar, y en segundo lugar los clubes de juegos de mesa que
> quieren nivelar partidas entre gente de distinta experiencia.
>
> El alcance es una prueba de concepto: Catan base, tres o cuatro jugadores, y solo la fase
> de colocación inicial. Decidí acotarlo ahí a propósito, porque seguir la partida entera
> multiplica el problema y no aporta más al usuario.

---

## 3 · Los datos (45 segundos)

> No existe una API pública de partidas de Catan, así que los datos los genero yo, como
> acordamos.
>
> Tengo dos generadores. Uno construye tableros válidos: reparte los 19 terrenos y las 18
> fichas numéricas respetando las reglas, incluida la de no dejar dos números rojos juntos,
> y coloca los nueve puertos. El otro es un simulador de mini-partidas.
>
> Aquí está la parte importante del diseño. Mi primera idea fue predecir la producción
> esperada de recursos, pero me di cuenta de que eso **se calcula con una fórmula exacta**:
> los pips entre 36. El modelo habría sacado un R² de uno sin aprender nada, porque le
> estaría dando la respuesta en la pregunta.
>
> Así que cambié la variable objetivo. Ahora el simulador juega 20 rondas desde cada
> colocación, tirando dados, cobrando recursos, construyendo lo que alcanza y cambiando en
> el banco cuando le sobra algo. La variable objetivo son los **puntos de victoria
> alcanzados**, promediados sobre 40 partidas. Eso sí depende de cosas que ninguna fórmula
> captura: los dados caen en enteros, construir cuesta combinaciones exactas y el comercio
> tiene un precio.

[Si pregunta por el volumen: 200 tableros, unas 193 parejas candidatas por tablero, casi
39 000 filas y 40 variables.]

---

## 4 · Una corrección de alcance que cambió el proyecto (45 segundos)

> Al principio evaluaba vértices de uno en uno, y encontré un problema: **un vértice tiene
> madera y ladrillo a la vez en solo el 9 % de los casos.** Tiene sentido, porque toca tres
> hexágonos como máximo.
>
> Pero en Catan no colocas un poblado, colocas dos. Así que pasé a modelar **la pareja**.
> Una pareja toca hasta seis hexágonos, y ahí esa combinación sube al 48 %.
>
> El cambio simplificó el proyecto en vez de complicarlo, y lo dejó más fiel al juego.

---

## 5 · Ingeniería de variables (1 minuto)

> Tengo 40 variables en tres fases.
>
> Las directas son los pips por recurso, cuántos hexágonos toca, si tiene puerto.
>
> Las de cruce son las que de verdad importan, y salen de las reglas del juego. Un camino
> cuesta una madera y un ladrillo, así que lo que limita no es la suma sino **el mínimo**
> entre los dos: con ocho pips de madera y uno de ladrillo construyes al ritmo del
> ladrillo. La de ciudad va ponderada, porque cuesta dos trigos y tres minerales, no uno de
> cada uno.
>
> Y las de dominio son las más trabajadas. La principal es la producción efectiva: un
> recurso que te sobra no se pierde, pero se cambia a cuatro por uno, o a dos por uno si
> tienes el puerto. Así que el excedente cuenta, pero descontado por su tasa de cambio.
>
> También tengo turnos estimados hasta cada construcción, espacio para expandirse, y tres
> que solo existen a nivel de pareja: si los dos poblados comparten hexágono, la distancia
> entre ellos, y la complementariedad, que es cuántos recursos aporta la pareja que ninguno
> de los dos tenía por su cuenta.

---

## 6 · Lo que encontré (1 minuto)

> Tres resultados.
>
> **Primero: los pips no predicen.** La regla que usa todo jugador en la mesa es ponerse
> donde haya más puntitos. A nivel de pareja, la correlación entre pips y puntos es de
> 0.14. Casi nada.
>
> **Segundo: lo que predice es la combinación.** Tomando solo las parejas de entre 17 y 21
> pips, o sea a igualdad de producción, las que completan madera con ladrillo sacan un 22 %
> más de puntos. Ese es el argumento del proyecto: si los pips predijeran bien, mi app
> sobraría, porque bastaría con contar puntitos.
>
> **Tercero, y este me gustó.** Yo tenía la intuición, por jugar, de que concentrar un
> recurso y tener su puerto dos por uno es una buena jugada. En la correlación simple salía
> **negativa**. Pero al meterla en la regresión el coeficiente sale **positivo**.
>
> La explicación es que los puertos están en la costa, y los vértices costeros tocan menos
> hexágonos, así que producen menos. La correlación mezclaba dos efectos contrarios. La
> regresión los separa porque controla por la producción al mismo tiempo.

---

## 7 · El modelo (45 segundos)

> Regresión lineal, siguiendo lo que comentaste en clase.
>
> Probé dos versiones. Con las 40 variables da un R² de 0.656. Con 12 variables escogidas
> da 0.633. Veintitrés milésimas de diferencia, y a cambio el modelo compacto tiene
> coeficientes que se pueden leer en voz alta. **Me quedé con el compacto**, porque los
> coeficientes son literalmente la explicación que la app le da al usuario.
>
> La partición es por tablero, no por fila, porque las 193 parejas de un mismo tablero
> comparten los mismos hexágonos.
>
> Y añadí la métrica que de verdad importa, porque la app no predice, **elige**. En cada
> tablero de prueba comparé la pareja que recomienda el modelo contra la que elegiría un
> jugador por pips. El modelo saca 7.5 puntos de promedio, los pips 6.4, el tope alcanzable
> es 8.6 y elegir al azar da 4.6. **El modelo captura el 73 % del margen disponible; elegir
> por pips captura el 45 %.**

---

## 8 · No supervisado (30 segundos)

> Para las estrategias usé agrupamiento. La primera versión agrupaba por el reparto de
> recursos, pero eso solo separa "qué recurso tienes más", y los grupos sacaban los mismos
> puntos. Cambié la entrada a lo que la pareja **puede construir**, y ahí sí salieron cuatro
> familias con resultados distintos.
>
> Expansión, con 5.6 puntos. Ciudades y desarrollo, 5.1. Puerto, 4.3. Y desequilibrada, 3.7.
>
> Dos cosas interesantes. La de puerto es la que **menos produce** de todas y aun así no es
> la peor. Y la desequilibrada, la peor, es justo la que elige quien se guía solo por los
> pips.

---

## 9 · La demostración (1 minuto)

[Enseñar la app en pantalla, en este orden.]

> La app tiene tres pasos.
>
> **Uno, tu tablero.** Haces clic en un hexágono y ajustas su terreno y su número. Los nueve
> puertos se ven alrededor.
>
> **Dos, quién ya colocó.** Si no eres el primero, marcas con clic los vértices que ya
> tomaron. La app descarta esos y sus vecinos por la regla de distancia mínima.
>
> **Tres, la recomendación.** Salen tres opciones, y a propósito son de **estrategias
> distintas**: tres opciones de expansión no ayudan a decidir, tres familias distintas sí.
> Cada una muestra los dos poblados sobre el tablero, los puntos estimados, qué produce, por
> qué esa pareja, y qué hacer y qué evitar.

[Aquí el momento fuerte. Cambiar a "Segunda colocación".]

> Y esto resuelve el problema real de la colocación serpiente. Entre tu primer poblado y el
> segundo juegan todos los demás, así que es normal que te quiten el vértice que te
> recomendé. Entonces marcas dónde pusiste el primero, marcas lo que se ocupó, y la app ya
> no busca parejas: **busca el mejor compañero para el que ya tienes**.
>
> Y fíjate que al perder el compañero, **la estrategia recomendada cambia**. No te da otro
> vértice cualquiera, te dice que el plan de la partida es otro.

---

## 10 · Qué falta (20 segundos)

> Me falta el despliegue remoto, el documento y el video. Y como añadido, subir una foto del
> tablero vacío para que detecte terrenos y números; lo dejé para el final a propósito,
> porque la app funciona completa sin eso y no quiero que sea el cuello de botella.
>
> ¿Qué me recomiendas ajustar?

---

## Preguntas probables y cómo contestarlas

**¿Por qué una regresión y no un ensamble?**
> Porque con estas variables no hace falta: 12 variables dan 0.633 y 40 dan 0.656. Y si
> usara un ensamble perdería la explicación, que es el producto. La app le dice al usuario
> por qué recomienda algo, y eso salen de los coeficientes.

**¿Cómo evitaste la fuga de datos?**
> Partiendo por `tablero_id`. Un tablero entero va a entrenamiento o a prueba, nunca
> partido. Lo medí y en este caso la diferencia es pequeña, pero lo mantengo porque es como
> se usa el modelo de verdad: la app recibe tableros que nunca ha visto.

**El simulador juega solo, sin rivales. ¿Eso no invalida los resultados?**
> Es una limitación declarada. No hay bloqueos, ni ladrón completo, ni intercambio entre
> jugadores. Vale para **comparar parejas del mismo tablero entre sí**, que es lo único que
> la app necesita, no como pronóstico absoluto de una partida real.

**¿Y el ruido de los dados?**
> La variable objetivo ya es un promedio de 40 partidas. Medí la desviación repitiendo la
> misma pareja doce veces y da 0.11 puntos, frente a una variación natural de 1.5.

**¿Cuánto vale esto en la práctica?**
> Alrededor de un punto de victoria por partida frente a elegir por pips. En una partida que
> se gana con 10, es mucho.

---

## Recordatorios

- Lleva la app **corriendo** antes de empezar a hablar, no la abras en vivo.
- Si algo falla, ten a mano una captura de las tres recomendaciones.
- Cuando menciones un número, dilo despacio. Los números son lo que se queda.
- Termina preguntando qué ajustar. Es la parte más útil de la sesión.
