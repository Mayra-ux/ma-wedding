# Modo «como producción» en tu computadora

Para probar el recorrido real completo antes de desplegar (I-10; ADR 0030): invitación, proxy, API con panel y una base **propia de este modo**, con los límites, encabezados y tareas de producción. Sin HTTPS.

| Qué | Dónde | Como en producción |
|---|---|---|
| Invitación | `http://localhost:8080` (nginx, con los encabezados de `vercel.json`) | Vercel |
| API + panel | `http://localhost:8000` y `/admin/` (nginx → API, agrega `X-Forwarded-For`) | Render |
| Base | `db-prod`, volumen `ma-wedding_db-prod-data`, **sin puertos publicados** | Render Postgres |
| Respaldos | volumen `ma-wedding_respaldos-prod` (carpeta) o `s3-prueba` (S3 de prueba) | R2 |
| Tareas | `tareas-prod` (`backup`, `purge`, `restaurar`, …), a mano | Tareas cron |

**Tu lista real en este modo:** puedes importarla para probar; los datos quedan solo en el volumen local `ma-wedding_db-prod-data`, nunca en el repositorio. Cuando termines, bórralos con los comandos de la sección 7. Los enlaces apuntan a `http://localhost:8080`: no los envíes a nadie.

Todo en **PowerShell**, desde `C:\Repositorios\ma-wedding`.

## 1. Preparar (una vez)

1. **Puerto de la invitación.** Si tienes abierto tu servidor de desarrollo de la invitación (`python -m http.server 8080`), usa otro puerto para este modo **en cada ventana de PowerShell** donde lo manejes:
   ```powershell
   $env:INVITACION_PUERTO = "8081"
   ```
   Así la invitación queda en `http://localhost:8081` y los enlaces que genera el panel también. Si el 8080 está libre, no hace falta.
2. **Construir la imagen** (una sola para la API y las tareas; incluye el panel, `pg_dump` 16 y `age`):
   ```powershell
   docker compose --profile prod-local --profile prod-local-tareas build api-prod
   ```
3. **Llave de respaldos local** (fuera del repo y de OneDrive):
   ```powershell
   New-Item -ItemType Directory -Force C:\Users\mayoa\llaves-ma
   docker compose --profile prod-local run --rm --no-deps -v "C:\Users\mayoa\llaves-ma:/out" tareas-prod age-keygen -o /out/age-respaldos-local.txt
   ```
   Copia la línea `Public key: age1…` y agrégala a tu `.env`: `BACKUP_AGE_RECIPIENT=age1…`. El archivo `.txt` tiene la llave **privada**: no lo copies a ningún otro lado.
4. Tu `.env` ya tiene el login con Google local (`http://localhost:8000/api/v1/auth/google/callback`), las llaves y las listas de correos: este modo las usa tal cual.

## 2. Levantar

```powershell
docker compose stop api                                          # libera el puerto 8000 del modo de desarrollo
docker compose --profile prod-local up -d proxy-prod             # proxy, API y base (solo este modo)
docker compose --profile prod-local run --rm migrate-prod        # esquema (usuario de migraciones)
docker compose --profile prod-local ps                           # api-prod debe decir "healthy"
```

Si quieres datos ficticios en vez de tu lista: `docker compose --profile prod-local run --rm tareas-prod python -m app seed-dev`.

## 3. El recorrido real

1. **Panel:** abre `http://localhost:8000/admin/` en Chrome o Edge y entra con tu cuenta de Google.
2. **Importar:** *Importar* → elige tu Excel → lado por defecto → *Ver vista previa* → si el archivo tiene varias hojas, elige la hoja y vuelve a *Ver vista previa* → *Aplicar importación*.
3. **Enlace:** abre una invitación → *Generar enlace*. El enlace aparece en «Enlace de la invitación».
4. **Abrir:** pega el enlace (`http://localhost:8080/#t=…`, o `8081`) en otra ventana: aparecen el nombre y los lugares, y el token desaparece de la barra.
5. **Confirmar:** responde el formulario.
6. **Verlo en el panel:** recarga la invitación en el panel: cambian la respuesta, el historial y el resumen.

## 4. Pruebas de operación

- **Límite por IP con encabezado falsificado** (301 peticiones → 429). Tarda unos segundos:
  ```powershell
  cd api; uv run python tools/probar_proxy.py; cd ..
  docker compose --profile prod-local restart api-prod           # libera tu IP después
  ```
- **Respaldo** (cifrado con tu llave pública) y su lista:
  ```powershell
  docker compose --profile prod-local run --rm tareas-prod python -m app backup
  docker compose --profile prod-local run --rm tareas-prod python -m app listar-respaldos
  ```
- **Purga.** Con la fecha real de hoy no borra nada; las fechas del 5 abr y del 4 jun se prueban en las pruebas automáticas:
  ```powershell
  docker compose --profile prod-local run --rm tareas-prod python -m app purge
  ```
- **Encabezados de la invitación:** `curl.exe -sI http://127.0.0.1:8080/` muestra `X-Robots-Tag: noindex, nofollow`, HSTS y `frame-ancestors 'none'`.
- **La base no es accesible desde Windows:** `Test-NetConnection 127.0.0.1 -Port 5432` → `TcpTestSucceeded : False`.

## 5. Restaurar un respaldo (prueba de restauración)

El script `ops/local/restauracion.sh` corre **dentro** de los contenedores y arma las conexiones con tu `.env`: no escribes contraseñas. Cambia `<clave>` por una de `listar-respaldos` (la que termina en `.dump.age`).

```powershell
$clave = "<clave>"
# 1. Base nueva y vacía
docker compose --profile prod-local exec db-prod sh /ops/restauracion.sh crear ma_restaurada
# 2. Restaurar (la llave privada se monta solo para este comando)
docker compose --profile prod-local run --rm -v "C:\Users\mayoa\llaves-ma\age-respaldos-local.txt:/run/llave.txt:ro" tareas-prod sh /ops/restauracion.sh restaurar ma_restaurada $clave
# 3. Verificar: ejecuta la purga primero y compara los conteos con el informe del respaldo
docker compose --profile prod-local run --rm tareas-prod sh /ops/restauracion.sh verificar ma_restaurada $clave
# 4. Borrar la base de prueba
docker compose --profile prod-local exec db-prod sh /ops/restauracion.sh borrar ma_restaurada
```

El paso 3 debe terminar con `conteos coinciden`. `restaurar` se niega a cargar sobre una base con datos, revisa el sha256 del respaldo y avisa con un mensaje claro si la base no existe o si la llave no es la correcta.

## 6. Opcional: respaldo a un S3 de prueba (en lugar de R2)

`s3-prueba` es un servidor S3 local (versitygw) con credenciales ficticias y datos en memoria: se borran al apagarlo.

```powershell
docker compose --profile prod-local --profile prod-local-tareas up -d s3-prueba
$s3 = @("-e", "BACKUP_DIR=", "-e", "BACKUP_S3_ENDPOINT=http://s3-prueba:7070", "-e", "BACKUP_S3_BUCKET=respaldos", "-e", "BACKUP_S3_REGION=us-east-1", "-e", "BACKUP_S3_ACCESS_KEY_ID=ficticia-local", "-e", "BACKUP_S3_SECRET_ACCESS_KEY=ficticio-solo-local-s3")
docker compose --profile prod-local --profile prod-local-tareas run --rm @s3 tareas-prod python -m app backup
docker compose --profile prod-local --profile prod-local-tareas run --rm @s3 tareas-prod python -m app listar-respaldos
```

Para restaurar desde ahí, agrega `@s3` después de `run --rm` en los pasos 2 y 3 de la sección 5.

## 7. Apagar y borrar

```powershell
# Apagar (conserva la base y los respaldos locales del modo):
docker compose --profile prod-local --profile prod-local-tareas stop proxy-prod api-prod db-prod s3-prueba
# BORRAR la base y los respaldos de este modo (tu lista). Solo estos dos volúmenes:
docker compose --profile prod-local --profile prod-local-tareas rm -sf proxy-prod api-prod db-prod s3-prueba
docker volume rm ma-wedding_db-prod-data ma-wedding_respaldos-prod
# Volver al modo de desarrollo:
docker compose up -d api
```

No uses `docker compose down -v`: borraría también la base de desarrollo (`db-data`).

Cuando ya no la necesites, borra también `C:\Users\mayoa\llaves-ma\age-respaldos-local.txt`.
