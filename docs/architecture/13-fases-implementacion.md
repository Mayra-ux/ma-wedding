# 13. Fases de implementación y criterios de aceptación

Definición aceptada por Mayra en la validación de la Fase 3 (2 nov 2026). Cada fase requiere autorización explícita para empezar (CLAUDE.md §5) y se da por cerrada solo cuando cumple **todos** sus criterios. Ningún entorno distinto de producción usa datos reales.

## I-1 · Esqueleto, estructura y entorno local
- La invitación y sus recursos (`index.html`, `*.webp`, `og.jpg`, `orn-*.svg`, `vercel.json`) están en `invitacion/`, y sus hashes SHA-256 son **idénticos** a los de antes de moverlos (ADR 0020).
- El README documenta el cambio de Root Directory de Vercel a `invitacion/` (lo hace Mayra junto con el merge).
- `api/` y `panel/` no están dentro de `invitacion/`.
- `docker compose up` levanta la API y un Postgres local; `GET /health` responde 200.
- La imagen corre con usuario no root, tiene `HEALTHCHECK`, imagen base fijada por digest y apagado ordenado (se verifica inspeccionando la imagen y enviando SIGTERM).
- Existe `.env.example` solo con valores ficticios; `git status` no muestra `.env`.
- El hook de escaneo de secretos bloquea un commit de prueba que contiene un secreto ficticio.
- Los tests y el linter corren con un solo comando y pasan.
- En `api/uv.lock` no aparecen `opentelemetry-sdk` ni ningún paquete `opentelemetry-exporter-*`; `opentelemetry-api` se admite como dependencia transitiva inerte de FastAPI (ADR 0019). Lo verifica un test.

## I-2 · Esquema, migraciones y datos ficticios
- `migrate` crea el esquema desde cero con el usuario de migraciones y es repetible.
- El usuario de ejecución **no puede** crear ni alterar tablas (test).
- Tests de la DB que fallan como se espera: `adultos = 0`, pases ≠ adultos + niños, dos versiones vigentes, dos enlaces activos, código duplicado, lado, grupo o rol fuera del catálogo, rol repetido en la misma invitación, longitudes excedidas.
- Los datos de prueba son ficticios; una búsqueda en el repo no encuentra teléfonos con formato real.
- Dos respuestas simultáneas para la misma invitación terminan con exactamente una versión vigente y numeración consecutiva (la API bloquea la invitación con `SELECT … FOR UPDATE`; test).
- Ningún código de la aplicación fuera de la purga ejecuta `DELETE` sobre `invitacion` (test estático + guarda de SQLAlchemy).

## I-3 · Tokens y enlaces
- El token tiene 128 bits (22 caracteres base64url). En la DB solo hay HMAC + copia AES-256-GCM con identificador de llave; el token en claro no aparece en tablas ni en logs (test).
- Regenerar, revocar o archivar deja el token anterior en `404 enlace_no_valido`.
- No se genera enlace para invitaciones en revisión o archivadas (`409`).
- `rotate-keys` vuelve a cifrar todas las copias y recalcula los HMAC; los enlaces existentes siguen funcionando (test).
- El enlace descifrado tiene la forma `https://<dominio>/#t=<token>`.

## I-4 · API pública
- Tests con reloj simulado de cada estado: abierta (sin y con respuesta), cerrada (sin y con respuesta), desbloqueada, congelada (sin y con respuesta), inválida, revocada, archivada.
- El cierre ocurre exactamente en `2027-01-31T00:00-06:00` (ADR 0025; un segundo antes: abierta; en el instante: cerrada).
- `confirmados` fuera de rango → `422` sin escribir; `asiste=false` deja `confirmados=0` y las alergias vacías, y conserva el mensaje.
- Cada respuesta válida crea una versión; tres envíos = tres versiones con una sola vigente.
- Inválido, revocado y archivado devuelven cuerpos idénticos.
- Rate limiting por token y por IP probado (`429`); cuerpo de más de 4 KB → `413`; `Cache-Control: no-store` presente.
- La respuesta de lookup no contiene el código INV, IDs, teléfonos, categorías ni nota (test de esquema).
- Los logs de los tests no contienen el token ni el nombre usados.

## I-5 · Integración de la invitación (requiere aprobación visual previa)
- Con `/#t=<token válido>`: nombre y pases reales, y el token desaparece de la barra.
- Recargar en la misma pestaña conserva el estado; una pestaña nueva sin token muestra el mensaje (a).
- Los estados (a), (b), (c), "cerrada con respuesta" y "congelada" se ven según lo aprobado; (c) muestra la fecha límite global.
- En 390 y 1440 px, el resto de la página es idéntico píxel a píxel a la versión anterior (método ya usado: franjas + espaciador); consola limpia; sin scroll horizontal.
- Un nombre con `<script>` se muestra como texto.
- La CSP declarada no rompe nada (consola sin violaciones).
- Probado con un enlace ficticio abierto desde WhatsApp en iOS y Android.
- **Salida a producción (ADR 0024):** I-5 se une solo a `develop`. Pasa a `main` únicamente cuando la API esté desplegada (I-10) y `api-base`/CSP apunten a ella, los apellidos del aviso de privacidad estén resueltos y la prueba de WhatsApp en iOS y Android haya pasado.
- **Resultado (aprobado por Mayra):** estados aprobados visualmente en 390 y 1440 px. Comparación del resto de la página aceptada como **idéntico salvo ruido de renderizado ≤ 4/255** (la misma magnitud que aparece al comparar `develop` contra sí mismo). Ajustes de la aprobación: indicador «+»/«−» en el aviso de privacidad, error de guardado con el recuadro `.pending` y menor separación entre columnas apiladas de la sección. Queda pendiente solo la prueba de WhatsApp en iOS y Android (requiere la API desplegada).

## I-6 · Autenticación del panel
- Un correo fuera de las listas recibe `403` sin sesión; la planner recibe `403` en cada endpoint de escritura (test parametrizado).
- Sin `X-CSRF-Token` válido, o con `Origin` ajeno, toda escritura recibe `403`.
- La cookie es `__Host-`, `Secure`, `HttpOnly`, `SameSite=Strict`; el logout invalida la sesión en el servidor.
- Quitar un correo de la lista y reiniciar corta una sesión abierta.
- Los encabezados de seguridad de la API y del panel están presentes (test).
- **Resultado (cerrada, 20 nov 2026; aprobado por Mayra):** todos los criterios se cumplen con pruebas automáticas y Google simulado (406 pruebas en total), incluida una prueba de mutación que confirma que fallan si se quitan el chequeo de rol, el de CSRF o la revisión de las listas. Prueba real con Google en local (`http://localhost:8000/admin/`, Chrome): una cuenta de la lista de novios entra con el rol de novios, cerrar sesión regresa al botón de inicio y una cuenta fuera de las listas ve «Acceso denegado». Por ahora no hay correo de planner (`ADMIN_EMAILS_PLANNER` vacía); se agrega cuando Mayra lo tenga. Detalles de implementación: ADR 0005 y 0019 (notas de implementación).

## I-7 · API del panel
- CRUD con las validaciones M1–M14; archivar revoca el enlace y saca la invitación de la lista por defecto y de la exportación.
- Bajar pases por debajo de los confirmados → `409`.
- El desbloqueo antes del plazo → `409`; más allá del congelamiento → `422`; pedido después del congelamiento → `409` (ADR 0027). Con reloj simulado, la invitación desbloqueada pasa a abierta y vuelve a cerrada al vencer.
- Respuesta del admin permitida en cualquier momento: los novios no tienen congelamiento (ADR 0027).
- La planner no recibe enlaces ni tokens en ninguna respuesta, recibe `403` en toda escritura salvo marcar un recordatorio (hasta su cierre) y ve mensajes, historial y auditoría (ADR 0026; test).
- Los totales del resumen cuadran con la lista (test). La consulta de la lista queda en la auditoría.
- La API es el único punto de escritura de la DB (test).
- Toda escritura deja un evento de auditoría sin datos personales.
- **Resultado (cerrada, 20 nov 2026; aprobado por Mayra):** todos los criterios se cumplen con pruebas automáticas (542 en total), incluida una prueba de mutación que confirma que fallan si se quitan la lectura solo para novios, la comprobación de pases, el bloqueo del desbloqueo tras el congelamiento o el cierre de la planner. Ninguna de las 17 lecturas del panel entrega a la planner un token o un enlace. Cambio en la invitación: «congelada» usa el texto de «cerrada» (ADR 0027), idéntico píxel a píxel a ese estado en 390 y 1440 px; el resto de la página quedó idéntico salvo ruido de renderizado ≤ 4/255, y las capturas fueron aprobadas. Migración 0005: congelamiento de los invitados el 6 feb 2027 00:00, cierre de la planner el 7 mar 2027 00:00 y tabla `recordatorio_enviado`. Decisiones: ADR 0026 y 0027.

## I-8 · Importación y exportación
- Con un archivo ficticio con los encabezados exactos de la planner: altas, actualizaciones, error por código desconocido, revisión por "# Pases" inconsistente, lado inválido y teléfono inválido; aviso de duplicados y de teléfono faltante.
- La vista previa no escribe nada en la DB (test). Aplicar escribe todo o nada.
- Rol desde Comentario solo con coincidencia exacta; la columna Rol (separada por `;`) manda.
- La marca de revisión se quita sola al corregir adultos y niños.
- Reimportar el archivo exportado no cambia nada y no toca respuestas, alergias ni mensajes.
- Exportación: 19 columnas exactas y en orden, iguales para novios y planner (ADR 0026); "# Pases" calculado; ¿Asistirá? = Sí/No/vacío; sin archivadas; `=HYPERLINK(...)` neutralizado.
- **Resultado (cerrada, 20 nov 2026; aprobado por Mayra):** todos los criterios se cumplen con pruebas automáticas (616 en total), usando un xlsx ficticio con la estructura del archivo real (varias hojas, título en B1, encabezados en la fila 2) y CSV con `;` en Windows-1252. Reimportar lo exportado deja las tablas idénticas byte a byte, en xlsx y csv. Novios y planner exportan celdas idénticas; ninguna exportación contiene enlaces ni tokens, y la planner recibe `403` al importar. Once archivos maliciosos se rechazan con `413` o `415`, sin ningún error 500: bomba ZIP, macros, rutas con `..`, entidades XML, entre otros. La prueba de mutación confirma que las pruebas fallan si se quitan el rechazo de DTD y entidades, el control de bomba ZIP, el uso de «# Pases» solo en altas, la neutralización de fórmulas o el todo o nada. Hallazgo corregido: openpyxl no usa defusedxml en todos sus lectores, así que se rechaza cualquier XML del libro con `<!DOCTYPE>` o `<!ENTITY>`. gitleaks no encontró secretos. Decisiones: ADR 0028.

## I-9 · Panel React + Vite
- La API sirve el panel en `/admin/` con enrutado por hash; funciona sin reglas de reescritura.
- Flujos completos con datos ficticios: crear → enlace → WhatsApp (principal y alterno; marca enviado) → recordatorios → desbloquear → archivar → exportar.
- Estadísticas y filtros calculados en el navegador con la lista completa.
- La planner no ve enlaces ni tokens, ni botones de escritura salvo marcar recordatorios hasta su cierre. Ve mensajes, historial y auditoría, y usa WhatsApp solo para recordatorios sin enlace (ADR 0026; criterio corregido en I-9).
- Accesible por teclado; todo texto de usuario como texto; CSP de la API sin violaciones.
- **Resultado (cerrada, 23 nov 2026; aprobado por Mayra):** todos los criterios se cumplen con 683 pruebas automáticas (634 de pytest y 49 de Vitest). Cuatro pruebas de punta a punta corren en Chrome con Google simulado y la API real: el flujo completo de los novios con el texto aprobado del mensaje con enlace, el uso solo con teclado, la planner antes y después de su cierre del 7 mar, y el cierre de sesión a los 30 minutos sin actividad. En todas hubo cero violaciones de CSP (incluido Trusted Types) y cero errores de JavaScript. La prueba de mutación detectó los 9 cambios introducidos a propósito, entre ellos HTML en el mensaje del invitado, escrituras sin CSRF, el enlace visible para la planner, una URL de WhatsApp sin validar, la CSP sin Trusted Types y un script en línea. gitleaks no encontró secretos. Mayra aprobó las capturas de las 15 pantallas en 390 y 1440 px. Novedades en la API: `GET /admin/invitations/{codigo}/link/whatsapp`, solo para novios, y `ahora` en `/admin/config`. El panel se compila dentro de un contenedor de Node fijado por digest y la imagen final no incluye Node. Decisiones: ADR 0029.

## I-10 · Operación lista para desplegar (cambio de alcance, 23 nov 2026)
Por decisión de Mayra, en I-10 **no se despliega**: la aplicación queda completa para probarla en local y todo el código de operación queda listo (ADR 0030). Los criterios que solo se cumplen al desplegar pasan a la fase siguiente.

Criterios de I-10 (verificables en local):
- Restauración probada: respaldo → DB nueva → `purge` → la API arranca y los conteos coinciden.
- Simulación de fechas: con el reloj en el 6 feb los invitados ya no aceptan cambios y en el 7 mar la planner queda en solo lectura, mientras los novios siguen editando (ADR 0027); en el 5 abr no quedan teléfonos ni alergias (incluido el historial); en el 4 jun no quedan datos personales. Las ejecuciones son repetibles.
- Un fallo forzado de `purge` o `backup` genera una alerta (Healthchecks simulado); cada ejecución deja un informe de conteos. Sin URL configurada, las alertas están apagadas.
- Los respaldos tienen vencimiento absoluto (prefijo por fecha y borrado de lo vencido), van cifrados con age y se prueban contra una carpeta local y un destino S3 compatible de prueba, nunca contra R2 real.
- La IP del cliente detrás del proxy no se puede falsificar: 301 peticiones con `X-Forwarded-For` falso → 429.
- La imagen incluye `pg_dump` 16 y `age`; el flujo `imagen.yml` existe (manual, acciones fijadas por SHA) y no se ejecuta.
- `vercel.json` con encabezados de seguridad y `noindex`, sin romper la invitación (Chrome, 390 y 1440 px, sin violaciones de CSP).
- Modo «como producción» en local (compose, perfil `prod-local`): invitación, proxy, API con panel y DB propia; recorrido real importar → enlace → abrir → confirmar → verlo en el panel.
- Guía de operación para el despliegue futuro (`docs/operacion/guia-despliegue.md`).
- **Resultado (cerrada, 23 nov 2026; aprobado por Mayra):** todos los criterios locales se cumplen, con 752 pruebas automáticas (703 de pytest y 49 de Vitest), y gitleaks no encontró secretos.
  - **Fechas y purga:** la simulación del 6 feb, 7 mar, 5 abr y 4 jun da resultados idénticos en dos corridas sobre bases nuevas. La purga corre con el usuario de ejecución, es idempotente y revierte todo si falla.
  - **Modo «como producción»:** la imagen trae `pg_dump` 16 (PGDG, llave verificada por huella) y `age`, sin curl, gpg ni Node. Con datos ficticios se recorrió importar → enlace → abrir → confirmar → verlo en el panel, con cero violaciones de CSP y cero errores de JavaScript en los dos orígenes.
  - **Respaldo y restauración:** el respaldo cifrado con `age` real se restauró, desde una carpeta y desde un S3 de prueba (versitygw), en una base nueva; `verificar-restauracion` dio «conteos coinciden» y la API arrancó sobre la base restaurada.
  - **Firma S3:** pasa los 4 ejemplos oficiales de AWS, y el servidor real rechaza un secreto equivocado.
  - **IP del cliente:** 301 peticiones con `X-Forwarded-For` falso dan 429, en pruebas y en vivo contra nginx.
  - **Alertas:** los fallos forzados de `purge` y `backup` generan alerta con un Healthchecks simulado.
  - **Invitación:** `vercel.json`, con encabezados de seguridad y `noindex`, no rompe la invitación (Chrome, 390 y 1440 px); llega a `main` con todo lo demás.
  - **Imagen:** el flujo `imagen.yml` está creado (manual, acciones fijadas por SHA) y no se ejecutó.
  - **Hallazgos corregidos:**
    - el usuario de ejecución no podía hacer `pg_dump`: la migración 0006 le da solo lectura de `alembic_version` y de las secuencias;
    - la purga no era idempotente después del 4 jun;
    - uvicorn con `FORWARDED_ALLOW_IPS="*"` permitía falsificar la IP;
    - los comandos de restauración de la guía fallaban en PowerShell 5.1: ahora usan `ops/local/restauracion.sh`.
  - **Prueba intermitente (abierta):** en la verificación previa al cierre, 1 de 7 corridas completas tuvo una prueba fallida (702 de 703); las 6 siguientes pasaron completas. No se registró qué prueba fue. Desde entonces `tools/check.py` guarda la salida completa de cada corrida en `api/logs/check-AAAAMMDD-HHMMSS.log` (ignorado por git) y pytest nombra cada falla (`-rfE`). Si se repite, se documenta la prueba, el error y la causa.
  - **Decisiones:** ADR 0030. Lo que solo se cumple al desplegar queda en la fase siguiente.

## Despliegue (fase futura, cuando Mayra lo autorice)
- Despliegue con la misma imagen en pruebas; Postgres sin acceso público (verificado desde fuera); TLS hacia la DB.
- Respaldo real a R2 con la regla de ciclo de vida verificada; alerta real de Healthchecks recibida.
- La prueba de 301 → 429 repetida contra el proxy real del proveedor (`TRUSTED_PROXY_HOPS`).
- Checklist de salida a producción firmado por Mayra: aviso de privacidad (con apellidos), textos de I-5, dominio, prueba de WhatsApp en iOS y Android, `api-base` y CSP de la invitación apuntando a la API desplegada, Root Directory de Vercel; solo entonces I-5 se une a `main` (ADR 0024).
