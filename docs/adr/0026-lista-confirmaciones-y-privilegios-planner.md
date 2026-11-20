# ADR 0026 — Lista de confirmaciones, resumen, recordatorios y privilegios de la planner

- **Estado:** Aceptado
- **Fecha:** 2026-11-20
- **Reemplaza parcialmente:** ADR 0005 (la planner ya no es "solo lectura + exportación"), ADR 0017 (la planner ve mensajes y auditoría, y usa WhatsApp para recordatorios) y ADR 0018 (columnas de la exportación de la planner)
- **Complementa:** ADR 0006, 0007, 0010, 0016, 0019 y 0027

## Contexto

Los novios y la planner necesitan consultar desde el panel, nunca con acceso directo a la base de datos, una lista completa de confirmaciones con los detalles de cada invitación, un resumen de totales y el historial de respuestas. Además, los novios decidieron que la planner vea todo salvo los enlaces personales, y que pueda enviar recordatorios por WhatsApp **sin enlace**.

## Decisión

### Lista de confirmaciones (`GET /api/v1/admin/invitations`)
- Una fila por invitación, ordenada por código; por defecto sin archivadas (`incluir_archivadas` las incluye).
- Campos: código INV, nombre a mostrar, adultos, niños autorizados, infantes, pases, estado (`pendiente`, `confirmada`, `no_asiste`), confirmados, fecha y origen (`invitado` o `admin`) de la última respuesta, alergias, mensaje, lado, grupo, roles, mesa, nota interna, No. de la planner, teléfono principal, contacto alterno, en revisión y motivos, desbloqueo y su vencimiento, archivada y su fecha, y los **indicadores** del enlace: activo (sí/no), enviado (sí/no, cuándo y por qué medio) y recordatorios enviados (cuántos, el último y su tipo).
- **Nunca** incluye la URL del enlace ni el token.
- Cada consulta de la lista queda en la auditoría (`consulta_lista`, con quién y cuándo, y `detalle = {incluir_archivadas, filas}`), sin datos personales.

### Resumen (`GET /api/v1/admin/summary`)
- Endpoint propio, calculado en el servidor a partir de la misma lista. El panel puede calcular subtotales filtrados en el navegador.
- Cuenta solo las invitaciones activas (las archivadas no cuentan, regla A12): invitaciones, pases asignados, personas confirmadas, niños autorizados e infantes, y totales `{invitaciones, pases, confirmados}` por estado, por lado, por grupo y por rol. Una invitación cuenta en cada uno de sus roles (ADR 0017).

### Historial (`GET /api/v1/admin/invitations/{codigo}/history`)
- Versiones de la más reciente a la más antigua, con fecha, origen, actor y mensaje. Lo ven los dos roles.

### Privilegios de la planner
- **Ve todo lo que ven los novios, salvo los enlaces personales:** lista completa (con mensaje y con los indicadores de envío del enlace), detalle, historial completo (con mensaje y actor), auditoría, resumen y configuración. La nota interna también es visible para ella.
- **No ve ni obtiene enlaces ni tokens** en ninguna respuesta. `GET …/link` es exclusivo de los novios y le responde 403, igual que generar, regenerar o revocar enlaces. Así no puede responder como si fuera un invitado.
- **No puede modificar datos:** ni crear, editar, archivar, restaurar, desbloquear, registrar respuestas ni gestionar enlaces.
- **Única escritura permitida:** marcar un recordatorio como enviado, hasta su cierre (ADR 0027), registrado en la auditoría con su correo como actor.
- **Exportación:** la planner exporta las **mismas 19 columnas** que los novios, incluido "Mensaje del invitado" (se aplica en I-8). La exportación no lleva enlaces.

### Recordatorios sin enlace
- La API arma el texto (`GET …/reminder?destino=principal|alterno`) y devuelve el tipo, el texto, el teléfono y la URL `wa.me`; el panel solo la abre. El texto **nunca** lleva el enlace.
- Según la fecha del servidor:
  - **Hasta el sábado 30 de enero de 2027 incluido** (`ahora < cierre_plazo`), tipo `confirmar`: «Hola, te recordamos confirmar tu asistencia a la boda de Mayra y Alejandro a más tardar el [fecha], desde el enlace que te enviamos por WhatsApp. Si no lo encuentras, escríbenos y te lo reenviamos.» La fecha sale de la configuración.
  - **Del 31 de enero al 6 de marzo de 2027** (`cierre_plazo ≤ ahora < cierre_planner`), tipo `evento`: «Hola, te recordamos que la boda de Mayra y Alejandro es el sábado 6 de marzo de 2027: ceremonia a la 1:00 p. m. en el Templo San Francisco de Asís y recepción a las 4:00 p. m. en La Viña Jardín de Eventos. ¡Te esperamos!»
  - Después del cierre de la planner: `409 recordatorios_cerrados`.
- Los textos son **provisionales** hasta su aprobación en I-9.
- Marcar como enviado (`POST …/reminder/sent`, con `destino`) lo pueden hacer los novios y la planner. Se guarda en la tabla `recordatorio_enviado` (tipo, destino, actor y fecha; nunca el teléfono), aparte de la marca de envío del enlace, para no pisarla y para conservar varios recordatorios por invitación. El actor se borra el 4 jun 2027 con los demás correos de administradores (ADR 0010).

### Reglas confirmadas en I-7
- **Escritura:** solo los novios modifican datos, y únicamente a través de la API del panel. Nadie tiene acceso directo de escritura a la base de datos: la API es el único punto de conexión, con el usuario de ejecución de privilegios mínimos (ADR 0019), y los cambios de estructura solo se hacen con migraciones por comando. Lo verifica un test.
- **Teléfonos:** 10 dígitos se guardan como `+52` + los 10 dígitos; los extranjeros, con su lada en formato E.164.
- **`PATCH /config` no se implementa:** las fechas se cambian por migración, porque la configuración es de solo lectura para el usuario de ejecución.
- Los novios registran respuestas en cualquier momento (ADR 0027). Las invitaciones archivadas se restauran antes de editarlas, desbloquearlas o registrarles una respuesta.

### Fuera de alcance (decisión de los novios)
- No se implementa ningún envío automático de mensajes ni integración con la API de WhatsApp Business.
- El mensaje del día de la boda lo enviará Mayra por su cuenta, con un script propio, a partir de la exportación de I-8.

## Consecuencias

- La planner puede trabajar con la misma información que los novios sin poder suplantar a un invitado.
- Los recordatorios quedan en un historial propio, separado del envío del enlace.
- La lista y el resumen salen de la misma consulta; un test verifica que los totales cuadran.
