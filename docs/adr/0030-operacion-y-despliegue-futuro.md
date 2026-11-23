# ADR 0030 — Operación y despliegue futuro: proveedor, dominio, respaldos y alertas

- **Estado:** Aceptado (decisiones para cuando se despliegue; **no se despliega en I-10**)
- **Fecha:** 2026-11-23
- **Complementa:** ADR 0002, 0004, 0010, 0013, 0019, 0021 y 0029

## Contexto

I-10 cambió de alcance a petición de Mayra: no se despliega todavía. La aplicación queda completa y se prueba en local, con todo el código de operación listo (`purge`, `backup`, restauración, alertas y la construcción de la imagen). Estas son las decisiones de los novios para el despliegue futuro, tomadas después de comparar proveedores con precios del 23 nov 2026 (Render, DigitalOcean y Google Cloud; Railway y Fly se descartaron).

## Decisión

### Proveedor (cuando se despliegue)
- **Render**, región **Ohio o Virginia** (no hay región en México). Un servicio web con la imagen, Render Postgres **16** (misma versión mayor que `pg_dump` en la imagen) sin acceso externo (lista de IPs vacía) y tres tareas cron: `backup`, `purge` y `migrate` (esta última se ejecuta a mano).
- **La imagen no la construye Render** (no admite el contexto adicional `panel-src`): la construye GitHub Actions (`.github/workflows/imagen.yml`, solo manual, acciones fijadas por SHA, procedencia firmada) y la publica en GHCR. Render la descarga **fijada por digest**.
- **Excepción acotada:** los respaldos internos de Render (restauración a un punto en el tiempo) duran **3 días** y no se configuran. Se acepta que, después de cada purga (5 abr y 4 jun 2027), esos respaldos internos conserven los datos borrados hasta 3 días más. Al apagar todo, la base se elimina junto con sus respaldos. Los respaldos propios (abajo) sí cumplen las fechas absolutas del ADR 0010.

### Dominio
- Un dominio **`.com` en Cloudflare Registrar**, con DNS en Cloudflare en modo **solo DNS** (sin el proxy de Cloudflare, para no alterar las IPs ni el TLS).
- **Invitación en Vercel** con el dominio propio: `https://<dominio>/#t=…` (`www` redirige a la raíz).
- **API y panel en `https://api.<dominio>`** (panel en `/admin/`, mismo origen que la API, ADR 0015).
- HSTS en la API (`SECURITY_HSTS=true`) y en la invitación (`vercel.json`), sin *preload*.

### Invitación sin indexar
- `X-Robots-Tag: noindex, nofollow` en `vercel.json` (resuelve la pregunta Q7). Junto con `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'` y HSTS (ADR 0019).

### Login con Google
- Un cliente OAuth de producción («Aplicación web») con la URI `https://api.<dominio>/api/v1/auth/google/callback`. La app se queda en **modo Prueba**, con los correos de los novios y de la planner como usuarios de prueba.

### Respaldos
- Volcado diario con `pg_dump` del usuario de ejecución (la migración 0006 le da solo **lectura** de `alembic_version` y de las secuencias, que el volcado necesita), cifrado con **age** hacia una llave pública. La llave privada nunca está en el proveedor.
- Destino fuera del proveedor: **Cloudflare R2**, con una regla de ciclo de vida por fecha absoluta por prefijo (`vence-2027-04-05/`, `vence-2027-06-04/`). El comando además borra lo vencido.
- **Firma S3 propia, sin dependencias nuevas** (ni boto3): AWS Signature V4 con la biblioteca estándar (`app/s3.py`), probada con los ejemplos oficiales de AWS.

### Alertas
- **Healthchecks.io, plan gratuito:** una URL de ping por tarea (`ALERT_PING_URL_BACKUP`, `ALERT_PING_URL_PURGE`). Avisa por correo si una tarea falla **o si no corrió**. Sin URL, las alertas están apagadas. Los avisos solo llevan conteos y el paso que falló.

### IP del cliente detrás del proxy
- Con `FORWARDED_ALLOW_IPS="*"`, uvicorn toma la IP **de más a la izquierda** de `X-Forwarded-For`, que escribe el cliente: el límite por IP se podía evadir. Ahora uvicorn corre con `--no-proxy-headers` y la API cuenta desde la **derecha** con `TRUSTED_PROXY_HOPS` (en Render, 1). `FORWARDED_ALLOW_IPS` deja de usarse.

## Consecuencias

- Costo estimado en Render: ~US$16 al mes (~US$112 de diciembre a junio), más el dominio. R2 y Healthchecks, gratis dentro de sus límites.
- Salir de Render es desplegar la misma imagen en otro lugar y restaurar un respaldo (`restaurar` + `verificar-restauracion`).
- El paso a paso del despliegue, el checklist de salida y el plan post-boda están en `docs/operacion/guia-despliegue.md`.

## Pendientes

- Compra del dominio, creación de las cuentas (Render, Cloudflare, Healthchecks) y del cliente OAuth de producción: los hace Mayra al desplegar.
- Confirmar en el entorno de pruebas si el usuario por defecto de Render puede crear roles; si no, ese usuario hace de migrador y solo se crea `ma_app` (doc 11).
- Precios de Render y Google tomados de fuentes secundarias (las páginas oficiales no se pudieron leer): confirmarlos en la calculadora antes de contratar.
