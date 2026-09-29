/**
 * Nombres cortos para los tipos generados del OpenAPI.
 *
 * Aquí no se define ningún campo: todo sale de `esquema.d.ts`, que se regenera con
 * `npm run api:tipos` cada vez que cambia el backend (AGENTS.md §6).
 */
import type { components } from './esquema';

type Esquemas = components['schemas'];

export type Tablero = Esquemas['Tablero'];
export type Hexagono = Esquemas['Hexagono'];
export type Puerto = Esquemas['Puerto'];
export type Terreno = Hexagono['terreno'];
export type Salud = Esquemas['Salud'];
export type Opcion = Esquemas['Opcion'];
export type PeticionRecomendar = Esquemas['PeticionRecomendar'];
export type RespuestaRecomendar = Esquemas['RespuestaRecomendar'];
export type PeticionChat = Esquemas['PeticionChat'];
export type RespuestaChat = Esquemas['RespuestaChat'];
export type Destino = Esquemas['Destino'];
export type MensajeChat = Esquemas['Mensaje'];
export type EstadoColocacion = Esquemas['EstadoColocacion'];
export type RespuestaVision = Esquemas['RespuestaVision'];
export type TableroConAvisos = Esquemas['TableroConAvisos'];
