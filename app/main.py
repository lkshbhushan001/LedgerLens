"""FastAPI application entry point.

Sets up lifespan management (Qdrant collection initialisation),
global middleware (CORS, structured logging), exception handlers,
and router registration.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.db.database import engine, Base
from app.core.config import settings
from app.core.exceptions import AppException
from app.services.embeddings import get_vector_size
from app.services.vector_store import vector_store
from app.utils.logging_config import configure_logging
from app.services.cache import semantic_cache
from app.routers import auth, health, ingestion, query, evaluation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure Qdrant collection exists with correct vector size.
    Shutdown: close vector store connections.
    """
    configure_logging(debug=settings.DEBUG)
    logger.info("Starting %s in %s mode", settings.APP_NAME, settings.ENVIRONMENT)

    vector_dim = get_vector_size()
    logger.info("Embedding model vector size: %d", vector_dim)

    await vector_store.ensure_collection(vector_size=vector_dim)
    logger.info("Vector store ready: %s", settings.QDRANT_COLLECTION)

    await semantic_cache.initialize_index(vector_dim=vector_dim)
    logger.info("Semantic cache ready")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    logger.info("Shutting down")
    await vector_store.close()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handler for domain errors
    @app.exception_handler(AppException)
    async def _app_exception_handler(request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    # Routers
    app.include_router(auth.router)
    app.include_router(health.router)
    app.include_router(ingestion.router)
    app.include_router(query.router)
    app.include_router(evaluation.router)

    return app


app = create_app()
