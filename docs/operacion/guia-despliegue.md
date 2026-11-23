# Guía de operación: despliegue futuro, salida a producción y plan post-boda

Para Mayra, cuando decida desplegar (ADR 0030). **Hoy no se despliega nada.** Los pasos están en el orden en que hay que hacerlos; ninguno se puede saltar. Donde dice `<dominio>`, va el dominio que compres (por ejemplo, `nombre.com`).

Reglas que aplican a toda la guía:
- Ningún valor real (llaves, contraseñas, correos, URLs de ping) se escribe en el repositorio, en un commit ni en un chat. Van solo en el gestor de secretos de Render y en tu gestor de contraseñas.
- Los archivos de llaves se guardan **fuera** del repositorio y **fuera de OneDrive** (para que no se sincronicen a la nube).
- Ningún enlace real se envía a invitados hasta terminar el checklist de salida (sección 6; ADR 0021 y 0024).

## 1. Cuentas que necesitas

| Servicio | Para qué | Plan |
|---|---|---|
| Cloudflare | Comprar el dominio `.com`, su DNS y el almacenamiento R2 de los respaldos | Registrar a precio de costo; R2 gratis hasta 10 GB |
| Render | API + panel (servicio web), Postgres 16 y tres tareas cron | Espacio Hobby; Starter (~US$7), Postgres basic-256mb (~US$6), tareas (US$1 mínimo c/u) |
| Healthchecks.io | Alertas de `backup` y `purge` por correo | Gratuito |
| GitHub | Construir la imagen y publicarla en GHCR (ya tienes la cuenta) | Gratis en repositorio público |
| Google Cloud | Cliente OAuth de producción (ya tienes el proyecto) | Gratis |
| Vercel | La invitación con el dominio propio (ya está ahí) | Hobby |

Confirma los precios en la calculadora de cada proveedor antes de contratar: los de Render salieron de fuentes secundarias (23 nov 2026).

## 2. Llaves, fuera del repositorio

Crea una carpeta solo tuya, por ejemplo `C:\Users\mayoa\llaves-ma\`, que **no** esté dentro de OneDrive ni del repositorio.

1. **Llaves de tokens y de sesión** (producción, nuevas; nunca las de tu `.env` local):
   ```powershell
   cd C:\Repositorios\ma-wedding\api
   uv run python -m app generar-llaves --env-file C:\Users\mayoa\llaves-ma\produccion.env
   ```
   Escribe `TOKEN_HASH_KEY`, `TOKEN_ENCRYPTION_KEYS` y `SESSION_SECRET` sin mostrarlas.
2. **Llave de respaldos (age):** con la imagen local (modo «como producción», ver `modo-como-produccion.md`):
   ```powershell
   docker compose --profile prod-local run --rm --no-deps -v "C:\Users\mayoa\llaves-ma:/out" tareas-prod age-keygen -o /out/age-respaldos-produccion.txt
   ```
   La terminal muestra `Public key: age1…`: esa es la **pública** (va a Render). El archivo contiene la **privada**: solo se usa para restaurar.
3. Copia los dos archivos a tu gestor de contraseñas (y, si quieres, a una memoria USB guardada). Si se pierde la llave de cifrado de tokens, hay que regenerar y reenviar todos los enlaces; si se pierde la privada de age, los respaldos no se pueden abrir.

## 3. Orden exacto del despliegue

### 3.1 Dominio y DNS (Cloudflare)
1. Compra `<dominio>` en Cloudflare Registrar (un año alcanza hasta después de junio de 2027).
2. Todos los registros que agregues van en modo **solo DNS (nube gris)**, nunca con el proxy de Cloudflare: cambiaría la IP que ve la API y el TLS.

### 3.2 Respaldos (Cloudflare R2)
1. Crea un bucket **privado**, por ejemplo `ma-wedding-respaldos`.
2. En la configuración del bucket, agrega dos reglas de ciclo de vida **por fecha** (no por días):
   - prefijo `vence-2027-04-05/` → borrar objetos el **2027-04-05**;
   - prefijo `vence-2027-06-04/` → borrar objetos el **2027-06-04**.
3. Crea un token de API de R2 con permiso **Object Read & Write solo en ese bucket**. Guarda el *Access Key ID* y el *Secret Access Key* en tu gestor de contraseñas. El endpoint es `https://<id-de-cuenta>.r2.cloudflarestorage.com`.

### 3.3 Alertas (Healthchecks.io)
1. Crea dos *checks*: `backup` y `purge`, cada uno con periodo **1 día** y gracia **2 horas**, zona `America/Mexico_City`.
2. Integración por correo hacia tu cuenta.
3. Copia la *ping URL* de cada uno (son secretas).

### 3.4 Imagen (GitHub Actions)
1. Con el código de producción ya en `main` (sección 6), ve a *Actions* → **imagen** → *Run workflow* sobre `main`.
2. Al terminar, el resumen muestra `ghcr.io/mayra-ux/ma-wedding-api@sha256:…`. Esa referencia **con digest** es la que usarás en Render (no uses etiquetas).
3. En *Packages* de GitHub, deja el paquete **público** (no contiene secretos; el código ya es público) o, si lo prefieres privado, crea un token de solo lectura (`read:packages`) para Render.

### 3.5 Base de datos (Render Postgres)
1. Crea un Postgres **versión 16**, plan basic-256mb, en la región elegida (**Ohio o Virginia**; todos los servicios en la misma).
2. **Acceso externo:** déjalo con la lista de IPs **vacía**.
3. **Usuarios (una sola vez):** agrega temporalmente solo tu IP a la lista, conéctate con `psql` usando la URL externa y ejecuta el SQL de «Crear los usuarios en el proveedor» del doc 11 con contraseñas largas y aleatorias (de tu gestor de contraseñas). **Vuelve a vaciar la lista** de inmediato.
   - Si el usuario por defecto de Render no puede crear roles: ese usuario hace de migrador (dueño) y solo creas `ma_app`.
4. Arma las dos URLs **internas** con `?sslmode=require`:
   - migraciones: `postgresql://ma_migrator:<contraseña>@<host-interno>:5432/<base>?sslmode=require`
   - ejecución: `postgresql://ma_app:<contraseña>@<host-interno>:5432/<base>?sslmode=require`

### 3.6 Tareas y servicio (Render)
Todas usan la imagen `ghcr.io/…@sha256:…` de 3.4 y la misma región. Cada una recibe **solo** sus variables (sección 4).

1. **Tarea `migrate`** (cron con un horario que no llegue, p. ej. `0 0 1 1 *`; se ejecuta con *Trigger run*): comando `python -m app migrate`. Ejecútala una vez y revisa que diga `migrate: esquema en la última versión.`
2. **Servicio web `api`:** plan Starter (siempre encendido), *Health check path* `/health`, sin comando (usa el de la imagen). Dominio personalizado `api.<dominio>`; en Cloudflare, el CNAME `api` → el host `….onrender.com` que indique Render (solo DNS). Espera el certificado.
3. **Tarea `backup`:** horario `30 8 * * *` (UTC = 02:30 en México), comando `python -m app backup`.
4. **Tarea `purge`:** horario `15 9 * * *` (UTC = 03:15 en México), comando `python -m app purge`.

### 3.7 Login con Google (cliente de producción)
1. Google Cloud → *APIs y servicios* → *Credenciales* → *Crear ID de cliente de OAuth* → **Aplicación web**.
2. URI de redirección autorizada (exacta): `https://api.<dominio>/api/v1/auth/google/callback`.
3. Pantalla de consentimiento: **Externa**, en **modo Prueba**; alcances solo `openid` y `email`; usuarios de prueba: los correos de los novios y de la planner.
4. Copia el ID y el secreto a las variables del servicio web.

### 3.8 Invitación (Vercel)
1. En el proyecto de Vercel: *Domains* → agrega `<dominio>` y `www.<dominio>` (redirige a la raíz). En Cloudflare, los registros que pida Vercel (solo DNS).
2. Root Directory: `invitacion` (ya configurado).
3. El cambio de `api-base` y la CSP va en el merge a `main` (sección 6).

## 4. Variables por servicio (solo nombres)

| Variable | `api` | `backup` | `purge` | `migrate` |
|---|:-:|:-:|:-:|:-:|
| `DATABASE_URL` (ejecución, interna, `sslmode=require`) | ✔ | ✔ | ✔ | |
| `MIGRATION_DATABASE_URL` (migraciones) | | | | ✔ |
| `DB_RUNTIME_ROLE=ma_app` | ✔ | | | ✔ |
| `TOKEN_HASH_KEY`, `TOKEN_ENCRYPTION_KEYS`, `SESSION_SECRET` | ✔ | | | |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | ✔ | | | |
| `ADMIN_EMAILS_NOVIOS`, `ADMIN_EMAILS_PLANNER` | ✔ | | | |
| `PANEL_ORIGIN=https://api.<dominio>` | ✔ | | | |
| `INVITATION_ORIGIN=https://<dominio>` | ✔ | | | |
| `SECURITY_HSTS=true` | ✔ | | | |
| `TRUSTED_PROXY_HOPS=1` | ✔ | | | |
| `LOG_LEVEL=INFO` | ✔ | ✔ | ✔ | ✔ |
| `BACKUP_S3_ENDPOINT`, `BACKUP_S3_BUCKET`, `BACKUP_S3_REGION=auto` | | ✔ | | |
| `BACKUP_S3_ACCESS_KEY_ID`, `BACKUP_S3_SECRET_ACCESS_KEY` | | ✔ | | |
| `BACKUP_AGE_RECIPIENT` (pública) | | ✔ | | |
| `ALERT_PING_URL_BACKUP` | | ✔ | | |
| `ALERT_PING_URL_PURGE` | | | ✔ | |

Los límites (`RATE_LIMIT_*`, `MAX_BODY_*`) y las duraciones de sesión usan sus valores por defecto. `PANEL_DIR` ya viene en la imagen.

## 5. Verificaciones (en este orden)

1. `https://api.<dominio>/health` responde `{"status":"ok"}`.
2. Encabezados de la API: `curl -sI https://api.<dominio>/health` muestra `strict-transport-security`, `x-content-type-options`, `referrer-policy` y `content-security-policy`.
3. **La base no es accesible desde fuera:** desde tu equipo, `pg_isready -h <host-externo> -p 5432` (o `psql` con la URL externa) **falla**. Repite cada vez que toques la lista de IPs.
4. **IP detrás del proxy:** `uv run python tools/probar_proxy.py --url https://api.<dominio>` → `OK` (la petición 301 recibe 429). Tu IP queda limitada una hora en la API pública; reinicia el servicio si lo necesitas.
5. Panel: entra en `https://api.<dominio>/admin/` con tu cuenta; una cuenta fuera de las listas ve «Acceso denegado».
6. **Respaldo real:** *Trigger run* de `backup` → en R2 aparecen `vence-2027-04-05/ma-wedding-….dump.age` y su `.json`; Healthchecks marca `backup` en verde. Revisa en R2 que las dos reglas de ciclo de vida estén activas.
7. **Alerta forzada:** cambia temporalmente `BACKUP_S3_BUCKET` a un nombre que no existe y ejecuta `backup` → llega el correo de Healthchecks con `falló: subida`. Restaura el valor y vuelve a ejecutarlo.
8. **Purga:** *Trigger run* de `purge` → el log dice `fase: nada que borrar todavía`; Healthchecks en verde.
9. **Prueba de restauración** (antes de enviar invitaciones y otra vez antes del 30 ene): descarga en tu equipo el respaldo, o apunta el modo «como producción» a R2 con el token, y sigue «Restaurar un respaldo» de `modo-como-produccion.md`: `restaurar` → `verificar-restauracion` debe decir `conteos coinciden`.
10. **Invitación:** `curl -sI https://<dominio>/` muestra `x-robots-tag: noindex, nofollow`, HSTS y `content-security-policy: frame-ancestors 'none'`.

## 6. Checklist de salida a producción (lo firmas tú)

- [ ] Apellidos de los responsables en el aviso de privacidad (hoy `[APELLIDOS]`).
- [ ] Dominio comprado; DNS, HTTPS y HSTS funcionando (sección 5).
- [ ] En una rama: `api-base` = `https://api.<dominio>` en `invitacion/index.html` y `uv run python tools/csp_invitacion.py --actualizar` (cambia solo las dos líneas de la CSP y de `api-base`); `uv run python tools/check.py` sin fallos.
- [ ] Merge de las ramas I-5 … I-10 a `main`; Vercel publica `main`; la invitación en `https://<dominio>` carga sin errores en la consola.
- [ ] Imagen construida desde ese `main` (3.4) y desplegada por digest.
- [ ] `TRUSTED_PROXY_HOPS=1` y la prueba 301 → 429 en `OK` (5.4).
- [ ] La base no es accesible desde fuera (5.3).
- [ ] Respaldo real, alerta forzada y prueba de restauración en `OK` (5.6–5.9).
- [ ] Prueba desde **WhatsApp en iOS y en Android** con un **enlace ficticio** en `https://<dominio>/#t=…`: abre la invitación, el token desaparece de la barra, confirma y se ve en el panel. La vista previa no muestra nombres.
- [ ] Correo de la planner en `ADMIN_EMAILS_PLANNER` y como usuario de prueba de Google.
- [ ] Antes de los datos reales: si probaste con datos ficticios en Render, borra esa base y crea una nueva y vacía (3.5 y 3.6.1). Las llaves de producción de la sección 2 se conservan: nunca se usaron fuera de Render.
- [ ] Importar la lista real desde el panel; revisar la vista previa.
- [ ] Solo entonces: generar y enviar los enlaces reales.

## 7. Plan después de la boda

| Fecha | Qué pasa | Quién |
|---|---|---|
| 30 ene 2027 (incluido) | Último día del plazo de confirmación | Automático |
| 6 feb 2027 00:00 | Se congela el RSVP de los invitados | Automático |
| 7 mar 2027 00:00 | La planner queda en solo lectura | Automático |
| 1 al 4 abr 2027 | **Exportación final** desde el panel (tú) y un `backup` manual adicional (*Trigger run*); revisa que su `.json` tenga los conteos esperados | Tú |
| 5 abr 2027 | `purge` borra teléfonos y alergias (también del historial). Revisa el log (`telefonos N · alergias N`) y Healthchecks. **Borra la exportación final descargada** o reemplázala por una sin esas columnas. En R2, los respaldos `vence-2027-04-05/` desaparecen (verifícalo). Los respaldos internos de Render pueden conservar esos datos hasta el 8 abr (excepción del ADR 0030) | Automático + tú |
| 4 jun 2027 | `purge` borra el resto de los datos personales; `backup` ya no respalda y deja R2 vacío. Verifica el log y R2 | Automático + tú |
| 4 jun 2027, después | **Apagado:** borra en Render el servicio web, las tres tareas y la base (con ella se van sus respaldos internos); borra el bucket de R2 y los checks de Healthchecks; elimina el cliente OAuth de producción; borra las llaves de producción y la llave privada de age de tu gestor de contraseñas. Decide qué hacer con el dominio (renovación en noviembre de 2027) y con la invitación en Vercel | Tú |

## 8. Salir de Render (si hiciera falta)

La misma imagen corre en cualquier PaaS de contenedores. Pasos: crear Postgres 16 privado en el nuevo proveedor → `restaurar` el último respaldo en la base nueva → `verificar-restauracion` → desplegar la imagen por digest con las mismas variables (ajustando `TRUSTED_PROXY_HOPS` al proxy del nuevo proveedor y repitiendo la prueba 301 → 429) → cambiar el CNAME `api` → apagar lo de Render.
