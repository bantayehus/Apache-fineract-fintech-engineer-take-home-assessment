"""Shared FastAPI dependencies: auth, correlation ID, session."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session


async def get_correlation_id(
    x_correlation_id: Annotated[str | None, Header()] = None,
) -> str:
    return x_correlation_id or str(uuid.uuid4())


async def require_auth(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    # Simple bearer token for the assessment
    expected = f"Bearer {settings.auth_token}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


SessionDep = Annotated[AsyncSession, Depends(get_session)]
CorrelationDep = Annotated[str, Depends(get_correlation_id)]
AuthDep = Annotated[None, Depends(require_auth)]