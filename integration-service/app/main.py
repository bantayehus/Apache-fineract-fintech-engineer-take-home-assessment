"""Integration Service – orchestrates Fineract + Mock ERP with reliability guarantees."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import accounts, clients, loans, transactions, reconciliation
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.session import engine, init_db

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting Integration Service")
    await init_db()
    # Optional: run recovery sweep on startup
    from app.services.recovery import recovery_sweep
    await recovery_sweep()
    yield
    await engine.dispose()
    logger.info("Integration Service stopped")


app = FastAPI(
    title="Integration Service",
    description="Reliable financial integration between partners, Fineract and ERP",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router, prefix="/api", tags=["accounts"])
app.include_router(clients.router, prefix="/api", tags=["clients"])
app.include_router(loans.router, prefix="/api", tags=["loans"])
app.include_router(transactions.router, prefix="/api", tags=["transactions"])
app.include_router(reconciliation.router, prefix="/api", tags=["reconciliation"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "integration-service"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = request.headers.get("X-Correlation-ID")
    logger.exception("Unhandled error", extra={"correlation_id": correlation_id, "path": str(request.url)})
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc),
                "correlation_id": correlation_id,
            }
        },
    )