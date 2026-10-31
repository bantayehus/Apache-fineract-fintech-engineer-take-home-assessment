"""Mock ERP – owns the chart of accounts and journal entries."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import accounts, journal_entries
from app.core.config import settings
from app.db.session import engine, init_db
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting Mock ERP")
    await init_db()
    # Seed default chart of accounts
    from app.services.seed import seed_chart_of_accounts
    await seed_chart_of_accounts()
    yield
    await engine.dispose()
    logger.info("Mock ERP stopped")


app = FastAPI(
    title="Mock ERP",
    description="Accounting master – chart of accounts and journal entries",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(accounts.router, prefix="/api", tags=["accounts"])
app.include_router(journal_entries.router, prefix="/api", tags=["journal-entries"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "mock-erp"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", extra={"path": str(request.url)})
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc),
                "correlation_id": request.headers.get("X-Correlation-ID"),
            }
        },
    )