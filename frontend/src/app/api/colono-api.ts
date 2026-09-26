import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import type {
  PeticionChat,
  PeticionRecomendar,
  RespuestaChat,
  RespuestaRecomendar,
  Salud,
  Tablero,
} from './tipos';

/**
 * Único punto de contacto con el backend.
 *
 * Los componentes piden datos aquí y nunca arman URLs por su cuenta, así que
 * cambiar de servidor (local o Render) solo toca `environments/`.
 */
@Injectable({ providedIn: 'root' })
export class ColonoApi {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiUrl;

  salud(): Observable<Salud> {
    return this.http.get<Salud>(`${this.base}/health`);
  }

  tableroAleatorio(): Observable<Tablero> {
    return this.http.get<Tablero>(`${this.base}/tableros/aleatorio`);
  }

  recomendar(peticion: PeticionRecomendar): Observable<RespuestaRecomendar> {
    return this.http.post<RespuestaRecomendar>(`${this.base}/recomendar`, peticion);
  }

  chat(peticion: PeticionChat): Observable<RespuestaChat> {
    return this.http.post<RespuestaChat>(`${this.base}/chat`, peticion);
  }
}
