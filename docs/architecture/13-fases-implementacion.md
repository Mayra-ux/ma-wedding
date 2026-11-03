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

## I-2 · Esquema, migraciones y datos ficticios
- `migrate` crea el esquema desde cero con el usuario de migraciones y es repetible.
- El usuario de ejecución **no puede** crear ni alterar tablas (test).
- Tests de la DB que fallan como se espera: `adultos = 0`, pases ≠ adultos + niños, dos versiones vigentes, dos enlaces activos, código duplicado, lado, grupo o rol fuera del catálogo, rol repetido en la misma invitación, longitudes excedidas.
- Los datos de prueba son ficticios; una búsqueda en el repo no encuentra teléfonos con formato real.

## I-3 · Tokens y enlaces
- El token tiene 128 bits (22 caracteres base64url). En la DB solo hay HMAC + copia AES-256-GCM con identificador de llave; el token en claro no aparece en tablas ni en logs (test).
- Regenerar, revocar o archivar deja el token anterior en `404 enlace_no_valido`.
- No se genera enlace para invitaciones en revisión o archivadas (`409`).
- `rotate-keys` vuelve a cifrar todas las copias y recalcula los HMAC; los enlaces existentes siguen funcionando (test).
- El enlace descifrado tiene la forma `https://<dominio>/#t=<token>`.

## I-4 · API pública
- Tests con reloj simulado de cada estado: abierta (sin y con respuesta), cerrada (sin y con respuesta), desbloqueada, congelada (sin y con respuesta), inválida, revocada, archivada.
- El cierre ocurre exactamente en `2027-02-07T00:00-06:00` (un segundo antes: abierta; en el instante: cerrada).
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

## I-6 · Autenticación del panel
- Un correo fuera de las listas recibe `403` sin sesión; la planner recibe `403` en cada endpoint de escritura (test parametrizado).
- Sin `X-CSRF-Token` válido, o con `Origin` ajeno, toda escritura recibe `403`.
- La cookie es `__Host-`, `Secure`, `HttpOnly`, `SameSite=Strict`; el logout invalida la sesión en el servidor.
- Quitar un correo de la lista y reiniciar corta una sesión abierta.
- Los encabezados de seguridad de la API y del panel están presentes (test).

## I-7 · API del panel
- CRUD con las validaciones M1–M14; archivar revoca el enlace y saca la invitación de la lista por defecto y de la exportación.
- Bajar pases por debajo de los confirmados → `409`.
- El desbloqueo antes del plazo → `409`; más allá del congelamiento → `422`. Con reloj simulado, la invitación desbloqueada pasa a abierta y vuelve a cerrada al vencer.
- Respuesta del admin permitida tras el plazo; rechazada tras el congelamiento.
- La planner no recibe mensajes en el listado, el detalle ni el historial (test).
- Toda escritura deja un evento de auditoría sin datos personales.

## I-8 · Importación y exportación
- Con un archivo ficticio con los encabezados exactos de la planner: altas, actualizaciones, error por código desconocido, revisión por "# Pases" inconsistente, lado inválido y teléfono inválido; aviso de duplicados y de teléfono faltante.
- La vista previa no escribe nada en la DB (test). Aplicar escribe todo o nada.
- Rol desde Comentario solo con coincidencia exacta; la columna Rol (separada por `;`) manda.
- La marca de revisión se quita sola al corregir adultos y niños.
- Reimportar el archivo exportado no cambia nada y no toca respuestas, alergias ni mensajes.
- Exportación de los novios: 19 columnas exactas y en orden; de la planner: 18, sin Mensaje; "# Pases" calculado; ¿Asistirá? = Sí/No/vacío; sin archivadas; `=HYPERLINK(...)` neutralizado.

## I-9 · Panel React + Vite
- La API sirve el panel en `/admin/` con enrutado por hash; funciona sin reglas de reescritura.
- Flujos completos con datos ficticios: crear → enlace → WhatsApp (principal y alterno; marca enviado) → recordatorios → desbloquear → archivar → exportar.
- Estadísticas y filtros calculados en el navegador con la lista completa.
- La planner no ve mensajes, enlaces, WhatsApp ni auditoría.
- Accesible por teclado; todo texto de usuario como texto; CSP de la API sin violaciones.

## I-10 · Operación y cierre
- Despliegue con la misma imagen en pruebas; Postgres sin acceso público (verificado desde fuera); TLS hacia la DB.
- Restauración probada: respaldo → DB nueva → `purge` → la API arranca y los conteos coinciden.
- Simulación de fechas: con el reloj en el 7 mar no se aceptan cambios; en el 5 abr no quedan teléfonos ni alergias (incluido el historial); en el 4 jun no quedan datos personales. Las ejecuciones son repetibles.
- Un fallo forzado de `purge` o `backup` genera una alerta; cada ejecución deja un informe de conteos.
- Los respaldos tienen vencimiento absoluto configurado.
- Checklist de salida a producción firmado por Mayra: aviso de privacidad, textos de I-5, dominio, prueba de WhatsApp, Root Directory de Vercel.
