# 4. Flujos del panel administrativo

Basado en ADR 0003/0015, 0005, 0007/0016, 0008/0013, 0009/0018, 0010, 0017 y 0019. El panel lo sirve la API (mismo origen). Las escrituras llevan cookie de sesión y `X-CSRF-Token` ([06](06-autenticacion-autorizacion.md)). Toda acción relevante genera un evento de auditoría sin datos personales. Después del congelamiento (7 mar 2027) solo se permite leer y exportar.

## 4.1 El admin desbloquea una invitación

```mermaid
sequenceDiagram
  autonumber
  actor N as Novios
  participant P as Panel
  participant A as API
  participant D as PostgreSQL

  N->>P: Abre INV-014, que pidió cambiar su respuesta tarde
  P->>A: POST unlock para INV-014 hasta el 10 feb 23:59
  A->>A: Sesión válida, rol novios, CSRF válido
  alt Plazo aún abierto
    A-->>P: 409 plazo_aun_abierto
  else Fecha posterior al congelamiento
    A-->>P: 422 mas_alla_del_congelamiento
  else Válido
    A->>D: Guarda desbloqueada_hasta y el evento de auditoría
    A-->>P: 200 desbloqueada hasta el 10 feb
  end
  Note over A: Hasta esa fecha, lookup devuelve estado abierta para INV-014
```

Con rol planner, la API responde `403`. Tras el congelamiento, `409 rsvp_congelado` (ADR 0016).

## 4.2 El admin crea una invitación, genera su enlace y lo envía por WhatsApp

```mermaid
sequenceDiagram
  autonumber
  actor N as Novios
  participant P as Panel
  participant A as API
  participant D as PostgreSQL
  participant WA as WhatsApp

  N->>P: Nueva invitación, Familia Ejemplo, 2 adultos, 1 niño, roles, teléfono
  P->>A: POST invitations
  A->>A: Valida adultos ≥ 1, catálogos, longitudes, teléfono +52
  A->>D: Crea la invitación con el código INV-034 y pases 3
  A-->>P: 201 INV-034
  N->>P: Generar enlace
  P->>A: POST link para INV-034
  A->>A: Verifica que no esté en revisión ni archivada
  A->>A: Genera 128 bits, calcula el HMAC y cifra la copia con AES-256-GCM
  A->>D: Guarda el enlace activo y el evento de auditoría
  A-->>P: 201 enlace con t=token en el fragmento
  N->>P: Botón WhatsApp, teléfono principal o contacto alterno
  P->>P: Arma el texto con la plantilla y el enlace wa.me
  P->>A: POST link sent con origen whatsapp
  A->>D: Marca el enlace como enviado, con fecha
  P->>WA: Abre wa.me, los novios envían el mensaje manualmente
```

Si la invitación no tiene teléfono, el panel muestra un aviso y permite copiar el mensaje y marcarlo como enviado a mano. La plantilla del mensaje está pendiente (Q9).

## 4.3 El admin regenera, revoca o archiva

```mermaid
sequenceDiagram
  autonumber
  actor N as Novios
  participant P as Panel
  participant A as API
  participant D as PostgreSQL

  alt Regenerar
    N->>P: Regenerar el enlace de INV-034
    P->>A: POST link regenerate
    A->>D: Transacción: revoca el activo, crea uno nuevo, reinicia la marca de enviado
    A-->>P: 201 enlace nuevo
  else Revocar sin reemplazo
    P->>A: POST link revoke
    A->>D: Marca la fecha de revocación
    A-->>P: 200 sin enlace activo
  else Archivar la invitación
    P->>A: POST archive
    A->>D: Transacción: archivada_en = ahora, revoca el enlace
    A-->>P: 200 archivada, fuera de conteos y exportaciones
  end
  A->>D: Evento de auditoría
  Note over A: El token anterior responde 404 enlace_no_valido de inmediato
```

## 4.4 Importación del Excel de la planner (sin estado)

```mermaid
sequenceDiagram
  autonumber
  actor N as Novios
  participant P as Panel
  participant A as API
  participant D as PostgreSQL

  N->>P: Sube el archivo xlsx o csv
  P->>A: POST imports preview con el archivo
  A->>A: Lee columnas, con o sin Código INV al inicio
  loop Cada fila
    A->>A: Normaliza teléfonos, mapea Invitado de a Novia, Novio o Ambos
    A->>A: Rol desde la columna Rol separada por punto y coma, o desde Comentario si coincide exacto
    A->>A: Ignora Asistirá, Pases confirmados, Mensaje y Alergias
    A->>A: Clasifica en alta, actualización o error de código desconocido
    A->>A: Revisión si Pases del Excel distinto de adultos + niños, lado o teléfono inválido
    A->>A: Avisos de nombre duplicado o teléfono faltante
  end
  A-->>P: Resultado por fila, sin escribir nada en la DB
  N->>P: Revisa y confirma
  P->>A: POST imports apply con el mismo archivo
  A->>D: Transacción: aplica altas y actualizaciones, guarda Pases original, sin borrar nada
  A->>D: Evento de auditoría con los conteos
  A-->>P: Resumen e invitaciones del sistema que no venían en el archivo
```

Si una invitación con enlace activo queda en revisión, el enlace sigue funcionando y el panel avisa (regla D7). La marca de revisión se quita sola cuando se corrige la inconsistencia (ADR 0018).

## 4.5 Exportación

```mermaid
sequenceDiagram
  autonumber
  actor U as Novios o planner
  participant P as Panel
  participant A as API
  participant D as PostgreSQL

  U->>P: Exportar la lista
  P->>A: POST exports con formato xlsx o csv
  A->>A: Sesión, rol y CSRF válidos
  A->>D: Lee las invitaciones no archivadas, sus respuestas vigentes y roles
  alt Rol novios
    A->>A: 19 columnas, Código INV, 14 de la planner, Mensaje, Grupo, Rol, Alergias
  else Rol planner
    A->>A: 18 columnas, sin Mensaje del invitado
  end
  A->>A: Pases calculado, Asistirá Sí, No o vacío, neutraliza fórmulas
  A->>D: Evento de auditoría con quién y cuándo
  A-->>P: Archivo para descargar
  Note over U: El archivo sale del sistema y su borrado sigue el ADR 0010
```

## 4.6 Borrado programado del 5 abr y del 4 jun 2027

```mermaid
sequenceDiagram
  autonumber
  participant S as Programador del hosting
  participant J as Tarea de borrado
  participant D as PostgreSQL
  participant L as Canal de alertas

  Note over S,J: Diaria, idempotente, lee las fechas de la configuración, usuario de ejecución
  S->>J: Ejecuta el comando purge
  J->>D: Lee las fechas de borrado y la fecha actual
  alt Hoy ≥ 5 abr 2027
    J->>D: Transacción: borra teléfonos de Invitación y alergias de todas las versiones
  end
  alt Hoy ≥ 4 jun 2027
    J->>D: Transacción: borra invitaciones, incluidas las archivadas, versiones, roles, enlaces, sesiones y auditoría
  end
  alt Error
    J->>L: Alerta con el paso que falló, sin datos personales
  else Éxito
    J->>L: Informe de conteos por tipo
  end
  Note over S,D: Luego se apagan la API y la DB (paso manual)
```

Previo: congelamiento el 7 mar 2027 00:00; exportación y respaldo finales antes del 5 abr. El 5 abr hay que borrar la exportación final descargada o reemplazarla por una versión sin teléfonos ni alergias (ADR 0010).
