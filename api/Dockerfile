# syntax=docker/dockerfile:1
# Imagen única de la API (doc 11 de arquitectura, ADR 0019). Bases fijadas por digest.
# El panel (React + Vite, ADR 0015) se compila en una etapa de Node que NO llega a la imagen
# final. Su código entra como contexto adicional `panel-src` (compose: additional_contexts;
# a mano: docker build --build-context panel-src=../panel api).

ARG PYTHON_IMAGE=python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30
ARG NODE_IMAGE=node:24.22.3-slim@sha256:dc26ae92c9fb15cf6b1d63e20f0944b2efe0f115b20e00be48fb23fceb061c54
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0

FROM ${UV_IMAGE} AS uv

# ---- Etapa del panel: npm ci sin scripts de instalación y build de Vite ----
FROM ${NODE_IMAGE} AS panel
WORKDIR /panel
COPY --from=panel-src package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY --from=panel-src index.html vite.config.js ./
COPY --from=panel-src public/ ./public/
COPY --from=panel-src src/ ./src/
RUN npm run build

# ---- Etapa de dependencias ----
FROM ${PYTHON_IMAGE} AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /build
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# ---- Imagen final ----
FROM ${PYTHON_IMAGE} AS runtime
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY --from=panel /panel/dist/ /srv/panel/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]
STOPSIGNAL SIGTERM
# IPs de proxies de confianza para X-Forwarded-For (uvicorn lee esta variable). Se ajusta al
# elegir proveedor (I-10); la IP del cliente alimenta el rate limiting por IP (ADR 0019).
ENV FORWARDED_ALLOW_IPS=127.0.0.1
# Build del panel servido en /admin/ (app/panel.py).
ENV PANEL_DIR=/srv/panel
# Forma exec: uvicorn es PID 1 y recibe SIGTERM directamente; termina peticiones en curso.
# Sin access log de uvicorn (registra IP y consulta) ni encabezado `server`: el log propio
# usa una lista cerrada de campos (app/seguridad.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "20", "--proxy-headers", "--no-access-log", "--no-server-header"]
