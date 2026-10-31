"""HTTP client for the Mock ERP."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ERPClient:
    def __init__(self) -> None:
        self._base = settings.erp_base_url.rstrip("/")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        url = f"{self._base}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, json=json)
            if resp.status_code >= 400:
                logger.error("ERP error", extra={"status": resp.status_code, "body": resp.text[:500]})
            resp.raise_for_status()
            if resp.status_code == 204 or not resp.content:
                return {}
            return resp.json()

    async def create_account(
        self,
        *,
        external_reference: str,
        code: str,
        name: str,
        type_: str,
        currency: str = "RWF",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/accounts",
            json={
                "external_reference": external_reference,
                "code": code,
                "name": name,
                "type": type_,
                "currency": currency,
            },
        )

    async def list_accounts(self) -> list[dict[str, Any]]:
        result = await self._request("GET", "/api/accounts")
        return result if isinstance(result, list) else []

    async def create_journal_entry(
        self,
        *,
        external_reference: str,
        entry_date: datetime,
        lines: list[dict[str, Any]],
        description: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "external_reference": external_reference,
            "entry_date": entry_date.isoformat(),
            "lines": lines,
        }
        if description:
            payload["description"] = description
        return await self._request("POST", "/api/journal-entries", json=payload)

    async def get_journal_entry(self, external_reference: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/journal-entries/{external_reference}")


erp_client = ERPClient()