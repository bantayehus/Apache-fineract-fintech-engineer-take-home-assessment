"""HTTP client for the customized Apache Fineract instance."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class FineractError(Exception):
    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Fineract HTTP {status_code}: {body[:800]}")


class FineractClient:
    def __init__(self) -> None:
        creds = f"{settings.fineract_username}:{settings.fineract_password}"
        self._auth = base64.b64encode(creds.encode()).decode()
        self._base = settings.fineract_base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Basic {self._auth}",
            "Content-Type": "application/json",
            "Fineract-Platform-TenantId": "default",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        url = f"{self._base}{path}"
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            resp = await client.request(method, url, headers=self._headers, json=json, params=params)
            if resp.status_code >= 400:
                logger.error(
                    "Fineract error status=%s body=%s url=%s payload=%s",
                    resp.status_code,
                    resp.text[:1000],
                    url,
                    json,
                )
                raise FineractError(resp.status_code, resp.text)
            if resp.status_code == 204 or not resp.content:
                return {}
            return resp.json()

    # ----- GL Accounts (Part A) -----

    async def create_gl_account(
        self,
        *,
        name: str,
        gl_code: str,
        type_: int,
        usage: int = 1,
        manual_entries_allowed: bool = True,
        external_reference: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "glCode": gl_code,
            "type": type_,
            "usage": usage,
            "manualEntriesAllowed": manual_entries_allowed,
        }
        if external_reference:
            payload["externalReference"] = external_reference
        if description:
            payload["description"] = description
        return await self._request("POST", "/glaccounts", json=payload)

    async def get_gl_account_by_id(self, gl_id: int | str) -> dict[str, Any]:
        return await self._request("GET", f"/glaccounts/{gl_id}")

    # ----- Clients -----

    async def create_client(
        self,
        *,
        firstname: str,
        lastname: str,
        office_id: int = 1,
        external_id: str | None = None,
        active: bool = True,
        activation_date: str | None = None,
        date_format: str = "yyyy-MM-dd",
        locale: str = "en",
        legal_form_id: int = 1,
    ) -> dict[str, Any]:
        # Same shape as the Postman call that works on Fineract
        payload: dict[str, Any] = {
            "officeId": office_id,
            "firstname": firstname,
            "lastname": lastname,
            "active": active,
            "locale": locale,
            "dateFormat": date_format,
            "legalFormId": legal_form_id,
            "activationDate": activation_date or "2020-01-01",
        }
        if external_id:
            payload["externalId"] = external_id
        logger.info("Creating Fineract client payload=%s", payload)
        return await self._request("POST", "/clients", json=payload)

    async def get_client_by_external_id(self, external_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/clients/external-id/{external_id}")

    # ----- Loans -----

    async def create_loan_application(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/loans", json=payload)

    async def approve_loan(self, loan_id: int | str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/loans/{loan_id}?command=approve", json=payload)

    async def disburse_loan(self, loan_id: int | str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/loans/{loan_id}?command=disburse", json=payload)

    async def repay_loan(self, loan_id: int | str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/loans/{loan_id}/transactions?command=repayment", json=payload)

    async def get_loan_by_external_id(self, external_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/loans/external-id/{external_id}")

    async def get_loan(self, loan_id: int | str) -> dict[str, Any]:
        return await self._request("GET", f"/loans/{loan_id}")

    async def get_loan_transactions(self, loan_id: int | str) -> dict[str, Any]:
        return await self._request("GET", f"/loans/{loan_id}/transactions")


fineract_client = FineractClient()