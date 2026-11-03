# 4. Flujos del panel administrativo

Basado en ADR 0003, 0005, 0007, 0008/0013, 0009 y 0010. Todas las peticiones del panel llevan la cookie de sesión y, si modifican datos, el encabezado CSRF ([06-autenticacion-autorizacion.md](06-autenticacion-autorizacion.md)). Toda acción relevante genera un evento de auditoría.

## 4.1 El admin desbloquea una invitación

```mermaid
sequenceDiagram
  autonumber
  actor N as Novios
  participant P as Panel
  participant A as API
  participant D as PostgreSQL

  N->>P: Abre INV-014, que pidió cambiar su respuesta tarde
  P->>A: POST unlock para INV-014 con desbloqueo hasta el 10 feb 23:59
  A->>A: Sesión válida, rol novios, CSRF válido
  A->>A: La fecha es futura y el RSVP no está congelado
  A->>D: Guarda desbloqueada_hasta y el evento de auditoría
  A-->>P: 200 invitación desbloqueada hasta el 10 feb
  Note over A: Hasta esa fecha, lookup devuelve estado abierta para INV-014
```

Con rol planner, la API responde `403`. Después del congelamiento previo al borrado no se puede desbloquear (**sugerencia aceptada**, regla C6 de [05-reglas-de-negocio.md](05-reglas-de-negocio.md)).

## 4.2 El admin crea una invitación, genera su enlace y lo envía por WhatsApp

```mermaid
sequenceDiagram
  autonumber
  actor N as Novios
  participant P as Panel
  participant A as API
  participant D as PostgreSQL
  participant WA as WhatsApp

  N->>P: Nueva invitación, Familia Ejemplo, 2 adultos, 1 niño, teléfono
  P->>A: POST invitations
  A->>A: Valida adultos ≥ 1, catálogos y teléfono, normaliza a +52
  A->>D: Crea la invitación con el código INV-034 y pases 3
  A-->>P: 201 INV-034
  N->>P: Generar enlace
  P->>A: POST link para INV-034
  A->>A: Verifica que no requiera revisión
  A->>A: Genera 128 bits aleatorios, calcula el hash y cifra la copia
  A->>D: Guarda el enlace activo y el evento de auditoría
  A-->>P: 201 enlace https://dominio/ con fragmento t=token
  N->>P: Preparar mensaje de WhatsApp
  P->>A: GET whatsapp-message para INV-034
  A-->>P: Texto del mensaje y enlace wa.me con el teléfono +52
  N->>WA: Abre wa.me o pega el mensaje y lo envía manualmente
```

El texto del mensaje de WhatsApp lo definen los novios; no se inventa. Queda como pendiente.

## 4.3 El admin regenera o revoca un enlace

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
    A->>D: Transacción: revoca el enlace activo y crea uno nuevo
    A-->>P: 201 enlace nuevo
    Note over A: El token anterior responde 404 enlace_no_valido de inmediato
  else Revocar sin reemplazo
    N->>P: Revocar el enlace de INV-034
    P->>A: POST link revoke
    A->>D: Marca la fecha de revocación del enlace activo
    A-->>P: 200 sin enlace activo
  end
  A->>D: Evento de auditoría en ambos casos
```

## 4.4 Importación del Excel de la planner con filas en revisión

```mermaid
sequenceDiagram
  autonumber
  actor N as Novios
  participant P as Panel
  participant A as API
  participant D as PostgreSQL

  N->>P: Sube el archivo de la planner en xlsx o csv
  P->>A: POST imports con el archivo
  A->>A: Lee columnas, con o sin Código INV al inicio
  loop Cada fila
    A->>A: Normaliza teléfonos, mapea Invitado de al catálogo de lado
    A->>A: Rol desde la columna Rol, si no existe desde Comentario
    A->>A: Ignora Asistirá, Pases confirmados, Mensaje y Alergias
    alt Código INV existente
      A->>A: Resultado actualización
    else Sin código
      A->>A: Resultado alta, asigna un código nuevo
    else Código desconocido
      A->>A: Resultado error de fila
    end
    alt Pases del Excel distinto de adultos + niños, lado o teléfono inválido
      A->>A: Marca requiere revisión con su motivo
    end
  end
  A->>D: Guarda el lote en estado vista previa con el resultado por fila
  A-->>P: Resumen de altas, actualizaciones, errores y revisión
  N->>P: Revisa y confirma la aplicación
  P->>A: POST imports apply
  A->>D: Transacción: aplica altas y actualizaciones, sin borrar nada
  A->>D: Evento de auditoría
  A-->>P: 200 lote aplicado e invitaciones del sistema que no venían en el archivo
  Note over P: Las invitaciones en revisión no pueden generar enlace hasta corregirse
```

La vista previa antes de aplicar es una **sugerencia aceptada** que complementa al ADR 0009: evita aplicar un archivo equivocado.

Si una fila reimportada marca para revisión una invitación que **ya tiene enlace activo**, el enlace sigue funcionando y el panel solo muestra un aviso. La marca impide generar o regenerar el enlace hasta corregirla (**sugerencia aceptada**, regla E13).

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
  A->>A: Sesión válida, rol novios o planner, CSRF válido
  A->>D: Lee invitaciones, respuestas vigentes y catálogos
  A->>A: Arma las columnas Código INV, las 14 de la planner, Mensaje, Grupo, Rol, Alergias
  A->>A: Neutraliza celdas que empiezan con = + - o @
  A->>D: Evento de auditoría con quién y cuándo, sin el contenido
  A-->>P: Archivo para descargar
  Note over U: El archivo sale del sistema y su borrado sigue el ADR 0010
```

Antes del 5 abr la exportación incluye teléfonos y alergias. Después, esas columnas salen vacías porque los datos ya no existen.

## 4.6 Borrado programado del 5 abr y del 4 jun 2027

```mermaid
sequenceDiagram
  autonumber
  participant S as Programador del hosting
  participant J as Tarea de borrado
  participant D as PostgreSQL
  participant B as Respaldos externos

  Note over S,J: Se ejecuta a diario, es idempotente y lee las fechas de la configuración
  S->>J: Ejecuta el comando purge
  J->>D: Lee las fechas de borrado y la fecha actual
  alt Hoy ≥ 5 abr 2027
    J->>D: Transacción: borra los teléfonos de Invitación
    J->>D: Borra las alergias de Respuesta y de Versión de respuesta
    J->>D: Evento de auditoría con conteos, sin datos
  end
  alt Hoy ≥ 4 jun 2027
    J->>D: Transacción: borra invitaciones, respuestas, versiones, enlaces
    J->>D: Borra sesiones, lotes, filas de importación y auditoría
  end
  J-->>S: Registro con conteos únicamente
  Note over B: Los respaldos vencen en las mismas fechas (10-respaldos.md)
  Note over S,D: Luego se apagan la API y la DB (paso manual)
```

Pasos previos manuales, antes del 5 abr: congelar el RSVP, hacer la exportación final y el respaldo final. El 5 abr hay que borrar la exportación final descargada o reemplazarla por una versión sin teléfonos ni alergias (ADR 0010).
