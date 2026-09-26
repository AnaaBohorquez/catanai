# Especificación: `src/variables.py`

Módulo que calcula las variables de cada vértice de un tablero. Entrada: un tablero de
`tablero.generar_tablero()` y un vértice. Salida: un diccionario de variables numéricas.

**Regla que gobierna todo este módulo:** una variable solo sirve si **varía entre los 54
vértices del mismo tablero**. Cualquier cantidad que valga igual para todo el tablero
(el total de pips del tablero, cuántos hexágonos hay, el promedio) no puede explicar por
qué un vértice es mejor que otro, y no debe incluirse. Si hace falta usar una cantidad del
tablero, tiene que entrar combinada con algo propio del vértice.

---

## Función principal

```python
def variables_de_vertice(vertice: frozenset, tablero: dict) -> dict[str, float]:
    """Calcula todas las variables de un vértice. Las llaves son los nombres de abajo."""
```

Y un ayudante que las calcule para todos los vértices de un tablero de una pasada,
reutilizando lo que se pueda:

```python
def variables_del_tablero(tablero: dict) -> list[dict]:
    """Una fila por vértice, con las variables más un identificador del vértice."""
```

---

## Fase 1 — directas

| Variable | Definición |
|---|---|
| `pips_totales` | Suma de pips de los hexágonos del tablero que toca el vértice |
| `num_hexagonos` | Cuántos hexágonos del tablero toca: 1, 2 o 3. Distingue orilla de interior |
| `num_recursos_distintos` | Cuántos recursos distintos produce, sin contar el desierto. De 0 a 3 |
| `pips_madera` | Pips que aportan sus hexágonos de bosque |
| `pips_ladrillo` | Ídem con colinas |
| `pips_trigo` | Ídem con campos |
| `pips_oveja` | Ídem con pastos |
| `pips_mineral` | Ídem con montañas |
| `toca_desierto` | 1 si alguno de sus hexágonos es desierto, 0 si no |
| `tiene_puerto` | 1 si el vértice pertenece a una arista con puerto, 0 si no |
| `puerto_generico` | 1 si su puerto es 3:1 |
| `puerto_especifico` | 1 si su puerto es 2:1 de algún recurso |

Usar `hexagonos_del_vertice()` y `puerto_del_vertice()` de `tablero.py`.

---

## Fase 2 — cruces

### Pares complementarios

Se usa el **mínimo** y no la suma porque construir exige ambos recursos: con 8 pips de
madera y 1 de ladrillo construyes al ritmo del ladrillo, no del promedio.

```python
par_camino      = min(pips_madera, pips_ladrillo)
par_ciudad      = min(pips_trigo / 2, pips_mineral / 3)   # la ciudad cuesta 2 y 3
trio_desarrollo = min(pips_trigo, pips_oveja, pips_mineral)
par_poblado     = min(pips_madera, pips_ladrillo, pips_trigo, pips_oveja)
```

`par_ciudad` va ponderada por el costo real. Un vértice con 4 de trigo y 3 de mineral
puede construir una ciudad por ronda de producción (4/2 = 2, 3/3 = 1, el cuello es el
mineral), y el mínimo simple no lo reflejaría.

### Control del suministro escaso

No usar "cuánta madera hay en el tablero": es constante para los 54 vértices. Lo que varía
es **qué fracción del suministro del tablero controla este vértice**.

```python
# Para cada recurso r:
control_r = pips_r_del_vertice / pips_r_en_todo_el_tablero    # 0 si el tablero no tiene r

control_suministro = suma de control_r sobre los cinco recursos
control_maximo     = máximo de control_r
```

Guardar `control_madera`, `control_ladrillo`, `control_trigo`, `control_oveja`,
`control_mineral`, más `control_suministro` y `control_maximo`.

### Otras

```python
# Qué tan concentrada está la producción en un solo recurso. De 0.33 a 1.
desequilibrio = max(pips_por_recurso.values()) / pips_totales      # 0 si pips_totales == 0

# El puerto 2:1 solo vale si es del recurso que más produces.
puerto_alineado = 1 si tiene puerto 2:1 y ese recurso es el de más pips del vértice, si no 0
```

---

## Fase 3 — dominio

### `produccion_efectiva`

Un recurso que te sobra no se pierde: se cambia en el banco, pero a un precio. Esta
variable descuenta el excedente por su tasa de cambio.

```python
equilibrio = pips_totales / 5      # lo que tendría cada recurso si estuviera repartido parejo

para cada recurso r:
    tasa_r = 2 si el vértice tiene el puerto 2:1 de r
             3 si tiene puerto 3:1
             4 en cualquier otro caso
    aporte_r = min(pips_r, equilibrio) + max(0, pips_r - equilibrio) / tasa_r

produccion_efectiva = suma de aporte_r
```

La parte del excedente vale una fracción, porque hay que cambiarla. Un vértice
concentrado en un solo recurso saca una `produccion_efectiva` bastante menor que sus pips
totales; uno equilibrado saca casi lo mismo.

### Turnos estimados hasta cada construcción

```python
cartas_por_ronda_r = pips_r / 36 * 4       # 4 tiradas por ronda, una por jugador

# Para una construcción que cuesta n_r de cada recurso r:
turnos = máximo sobre r de (n_r / cartas_por_ronda_r)
# Si algún cartas_por_ronda_r es 0 y esa construcción lo necesita, tope de 60
```

Generar `turnos_a_camino`, `turnos_a_poblado`, `turnos_a_ciudad`,
`turnos_a_carta_desarrollo`. Los costos están en `COSTOS` de `tablero.py`.

El tope de 60 es mayor que las 30 rondas de una partida: significa "no llegas".

### Espacio de expansión

```python
# Vértices legales para un poblado a uno o dos caminos de distancia,
# respetando la regla de distancia mínima de dos.
vertices_expansion_1 = cuántos hay a distancia 1 que sean legales
vertices_expansion_2 = cuántos hay a distancia 2 que sean legales
pips_vecinos_max     = pips del mejor de esos vértices
pips_vecinos_media   = pips promedio de esos vértices
```

Usar `vertices_adyacentes()` de `tablero.py`. Un vértice está a distancia 2 si es vecino
de un vecino y no es vecino directo.

### `espacio_ruta_larga`

El camino más largo son 2 puntos y necesita cinco caminos conectados. Un vértice acorralado
contra la costa no puede lograrlo aunque produzca bien.

```python
# Longitud de la cadena de aristas más larga que se puede tender desde este vértice,
# con tope de 6 para que el cálculo no se dispare.
espacio_ruta_larga = búsqueda en profundidad desde el vértice sin repetir aristas, tope 6
```

---

## Qué NO incluir

- `pips_relativos`, `ranking_pips` o cualquier división entre un promedio del tablero: son
  la misma columna reescalada por una constante dentro de cada tablero, no cambian el orden
  de los 54 vértices y quedan casi perfectamente correlacionadas con `pips_totales`, lo que
  estropea la interpretación de los coeficientes.
- `escasez_madera` entendida como "pips de madera en el tablero": constante para los 54
  vértices. La versión útil es `control_madera`, que sí varía.
- `tipo_puerto` como texto: para el modelo van las banderas numéricas
  `puerto_generico`, `puerto_especifico` y `puerto_alineado`.

---

## Verificación

Incluir `verificar_variables(tablero)` que lance `AssertionError` si:

- Los 54 vértices producen exactamente el mismo conjunto de llaves.
- Ningún valor es `None`, `NaN` ni infinito.
- `pips_totales` coincide con `pips_del_vertice()` de `tablero.py`.
- La suma de los cinco `pips_<recurso>` es igual a `pips_totales` menos los pips del
  desierto, que son 0.
- `par_camino <= min(pips_madera, pips_ladrillo)` y todas las variables de par son ≥ 0.
- `0 <= control_r <= 1` para todos los recursos.
- `produccion_efectiva <= pips_totales` siempre.
- **Ninguna variable tiene el mismo valor en los 54 vértices.** Si alguna lo tiene, es
  constante dentro del tablero y no sirve: hay que quitarla.

---

## Demostración al correr el módulo

Con `python src/variables.py`, generar un tablero con semilla 42 y mostrar:

1. Cuántas variables se calcularon y sus nombres.
2. La tabla de los cinco mejores vértices por `pips_totales`, con sus `par_camino`,
   `par_ciudad`, `produccion_efectiva` y `turnos_a_camino`.
3. El resultado de `verificar_variables()`.

---

## Reglas de implementación

- Nombres en español sin acentos, como en `tablero.py`.
- Docstrings en formato NumPy.
- Sin dependencias nuevas: solo la librería estándar y lo que ya está en `tablero.py`.
- No modificar `tablero.py`. Si hace falta algo de ahí que no existe, proponerlo antes.
- Empezar en modo plan, sin escribir código hasta que el plan esté aprobado.
