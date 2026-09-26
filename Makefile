.DEFAULT_GOAL := help
SHELL := /bin/bash

BACKEND  := backend
FRONTEND := frontend

.PHONY: help setup setup-backend setup-frontend dev dev-backend dev-frontend \
        test lint format dataset modelo openapi build up down logs clean

## help: lista los objetivos disponibles
help:
	@echo "Colono IA — objetivos disponibles:"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /' | column -t -s ':'
	@echo ""

# --- Instalación -----------------------------------------------------------

## setup: instala dependencias de backend y frontend
setup: setup-backend setup-frontend

## setup-backend: crea el entorno e instala el backend
setup-backend:
	cd $(BACKEND) && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

## setup-frontend: instala dependencias npm
setup-frontend:
	cd $(FRONTEND) && npm install

# --- Desarrollo ------------------------------------------------------------

## dev-backend: API en http://localhost:8000 (documentación en /docs)
dev-backend:
	cd $(BACKEND) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

## dev-frontend: interfaz en http://localhost:4200
dev-frontend:
	cd $(FRONTEND) && npm start

# --- Datos y modelo --------------------------------------------------------

## dataset: genera data/processed/parejas.csv (unos 25 minutos)
dataset:
	cd $(BACKEND) && python -m scripts.generar_dataset --tableros 200

## openapi: exporta el contrato de la API a openapi.json
openapi:
	cd $(BACKEND) && uv run python -m scripts.exportar_openapi

# --- Calidad ---------------------------------------------------------------

## test: corre las pruebas del backend
test:
	cd $(BACKEND) && pytest -q

## lint: revisa el estilo del backend
lint:
	cd $(BACKEND) && ruff check app tests

## format: aplica el formato automático
format:
	cd $(BACKEND) && ruff check --fix app tests

# --- Contenedores ----------------------------------------------------------

## build: construye las imágenes
build:
	docker compose build

## up: levanta todo (API en :8000, interfaz en :8080)
up:
	docker compose up -d

## down: apaga todo
down:
	docker compose down

## logs: sigue los registros
logs:
	docker compose logs -f

## clean: borra artefactos locales
clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/.pytest_cache
