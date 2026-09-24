# Colono IA

Recomendador de colocación inicial en Catan. Fotografía el tablero recién armado y
la app te dice dónde poner tus dos primeros poblados, y por qué.

Trabajo final del Módulo 5 del diplomado. Ana Bohórquez, 2026.

## El problema

La colocación inicial decide buena parte de la partida y se toma por intuición en
menos de un minuto. Sobre 200 tableros simulados, la pareja que recomienda el modelo
vale **un punto de victoria más** que la que elegiría un jugador guiándose por los
pips, que es el criterio habitual en la mesa.

## Arquitectura

```
├── backend/          FastAPI · dominio, modelo, visión, chat
├── frontend/         Angular · interfaz
├── notebooks/        EDA y modelado, reproducibles en Colab
├── modelos/          colono.joblib, generado por el notebook 02
├── data/processed/   parejas.csv, generado por scripts/generar_dataset.py
└── docs/             conceptos del juego y decisiones
```

## Arranque rápido

```bash
make setup          # instala backend y frontend
make dev-backend    # API en http://localhost:8000/docs
make dev-frontend   # interfaz en http://localhost:4200
```

O todo en contenedores:

```bash
make up             # API en :8000, interfaz en :8080
```

## La API

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/health` | Estado del servicio |
| GET | `/api/v1/modelo` | Variables y métricas del modelo |
| GET | `/api/v1/tableros/aleatorio` | Un tablero válido para probar |
| POST | `/api/v1/tableros/validar` | Revisa un tablero contra las reglas |
| POST | `/api/v1/recomendar` | **El endpoint central** |
| POST | `/api/v1/vision/tablero` | Lee el tablero de una foto |
| POST | `/api/v1/chat` | Pregunta sobre la recomendación |

Documentación interactiva en `/docs`.

## Regenerar datos y modelo

```bash
make dataset                      # ~25 min, 200 tableros
jupyter notebook notebooks/       # 01_eda.ipynb y luego 02_modelo.ipynb
```

## Documentación

- `AGENTS.md` — reglas, decisiones y trampas encontradas
- `docs/conceptos-catan.md` — el dominio del juego explicado
