# 3. Flujos del invitado

Basado en ADR 0007, 0008, 0011 y 0013. Los endpoints están detallados en [07-contratos-api.md](07-contratos-api.md).

- `POST /api/v1/public/invitation/lookup`: consulta la invitación (el token va en el cuerpo).
- `POST /api/v1/public/invitation/response`: guarda la respuesta (el token va en el cuerpo).

## 3.1 El invitado abre su enlace y confirma

```mermaid
sequenceDiagram
  autonumber
  actor G as Invitado
  participant W as Invitación (navegador)
  participant A as API
  participant D as PostgreSQL

  G->>W: Abre https://dominio/ con fragmento t=token
  Note over W: El fragmento no se envía al servidor
  W->>W: Lee t=token, lo guarda en memoria y sessionStorage
  W->>W: history.replaceState quita el token de la barra
  W->>W: Sección RSVP en estado de carga
  W->>A: lookup con el token en el cuerpo
  A->>A: Rate limit por IP, calcula el hash del token
  A->>D: Busca un enlace activo por hash
  D-->>A: Invitación, respuesta vigente (ninguna), configuración
  A->>A: Estado = abierta (antes de la fecha límite o desbloqueada)
  A-->>W: 200 nombre, pases, fecha límite, estado abierta, sin respuesta
  W->>W: Muestra el nombre y los pases como texto, stepper de 1 a pases
  G->>W: Elige SÍ ASISTIRÉ, confirma 2 de 3, escribe un mensaje
  W->>A: response con token, asiste, confirmados 2, mensaje
  A->>A: Valida token, plazo, 1 ≤ 2 ≤ pases, longitudes
  A->>D: Transacción: crea la versión 1 y la respuesta vigente
  D-->>A: OK
  A-->>W: 200 respuesta registrada
  W->>W: Muestra la confirmación con los datos guardados
```

## 3.2 El invitado modifica su respuesta

```mermaid
sequenceDiagram
  autonumber
  actor G as Invitado
  participant W as Invitación (navegador)
  participant A as API
  participant D as PostgreSQL

  G->>W: Vuelve a abrir el enlace o recarga la pestaña
  W->>W: Token del fragmento, o de sessionStorage si recargó
  W->>A: lookup con el token
  A->>D: Busca invitación y respuesta vigente
  A-->>W: 200 estado abierta, respuesta vigente asiste 2 de 3
  W->>W: Muestra la respuesta registrada con MODIFICAR RESPUESTA
  G->>W: MODIFICAR RESPUESTA, cambia a NO PODRÉ
  W->>A: response con token, asiste falso, confirmados 0
  A->>A: Valida plazo y regla asiste falso implica 0
  A->>D: Transacción: crea la versión 2 y reemplaza la respuesta vigente
  A-->>W: 200 respuesta registrada
  Note over D: La versión 1 queda en el historial (ADR 0007)
```

## 3.3 El invitado intenta exceder sus pases

```mermaid
sequenceDiagram
  autonumber
  actor G as Invitado
  participant W as Invitación (navegador)
  participant A as API
  participant D as PostgreSQL

  G->>W: Pulsa + en el stepper
  W->>W: El botón + se deshabilita al llegar a pases
  Note over G,W: La interfaz solo ayuda, no es la garantía
  G->>A: Petición manipulada con confirmados 5 y pases 3
  A->>D: Lee los pases de la invitación
  D-->>A: pases 3
  A->>A: 5 > 3, rechaza
  A-->>G: 422 confirmados_fuera_de_rango
  Note over A,D: Nada se escribe. La DB también rechazaría el valor
```

El invitado tampoco puede aumentar los pases ni agregar niños: la API pública no tiene ningún campo para hacerlo (ADR 0006).

## 3.4 Plazo vencido, token inválido o sin token

```mermaid
sequenceDiagram
  autonumber
  actor G as Invitado
  participant W as Invitación (navegador)
  participant A as API
  participant D as PostgreSQL

  alt Sin token en el fragmento ni en sessionStorage
    G->>W: Abre https://dominio/
    W->>W: No llama a la API
    W->>W: Sección RSVP muestra el mensaje (a)
  else Token inexistente o revocado
    G->>W: Abre el enlace con un token no válido
    W->>A: lookup con el token
    A->>D: Busca un enlace activo por hash
    D-->>A: Sin coincidencia
    A-->>W: 404 enlace_no_valido, respuesta uniforme
    W->>W: Borra el token de sessionStorage
    W->>W: Sección RSVP muestra el mensaje (b)
  else Token válido, plazo vencido, sin desbloqueo
    W->>A: lookup con el token
    A-->>W: 200 estado cerrada, con o sin respuesta
    alt Hay respuesta registrada
      W->>W: Muestra la respuesta registrada, sin MODIFICAR
    else No hay respuesta
      W->>W: Muestra el mensaje (c) con la fecha de la configuración
    end
  else Intenta enviar con el plazo vencido
    G->>A: response con el token
    A->>A: Fecha límite pasada y sin desbloqueo vigente
    A-->>G: 409 plazo_cerrado
  end
```

Textos (a), (b) y (c): ADR 0011, pendientes del canal de contacto y de la aprobación visual de I-5. En todos los casos, el resto de la invitación se muestra completo.
