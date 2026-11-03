"""Aplicación FastAPI. En I-1 solo expone el endpoint de salud."""

import logging

from fastapi import FastAPI, Response

from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    # Sin documentación interactiva pública: la API no expone su esquema.
    app = FastAPI(title="M&A RSVP API", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health", include_in_schema=False)
    def health(response: Response) -> dict[str, str]:
        response.headers["Cache-Control"] = "no-store"
        return {"status": "ok"}

    return app


app = create_app()
