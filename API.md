# Integration Service API Contract

Base URL (docker-compose): `http://localhost:8000`

All responses include a `correlation_id` (echoed from request header `X-Correlation-ID` or generated).

Authentication: Bearer token (simple shared secret for the assessment; replace with OAuth2 / mTLS in production).

## Common Error Format
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "external_reference already used with a different payload",
    "details": {},
    "correlation_id": "corr-..."
  }
}
```

## Endpoints

### GL Account Sync
`POST /api/accounts/sync`
```json
{
  "external_reference": "GL-1200",
  "code": "1200",
  "name": "Loan Receivable",
  "type": "ASSET",
  "currency": "RWF"
}
```
Idempotent on `external_reference`. Returns 200 (created or existing) or 409.

### Clients
`POST /api/clients`
```json
{
  "external_reference": "CLIENT-CREATE-001",
  "client_uid": "SME-000001",
  "firstname": "Acme",
  "lastname": "Trading Ltd",
  "office": "Kigali Main Office"
}
```
`GET /api/clients/{client_uid}`

### Loans
`POST /api/loans` – application (optionally approve in same call)
```json
{
  "external_reference": "LOAN-APP-001",
  "loan_reference": "LN-2026-000001",
  "client_uid": "SME-000001",
  "product": "SME Asset Finance",
  "principal": 5000000,
  "currency": "RWF",
  "term_months": 12,
  "interest_rate": 18.0
}
```

`GET /api/loans/{loan_reference}`

`POST /api/loans/{loan_reference}/disburse`
```json
{
  "external_reference": "DISB-001",
  "disbursement_date": "2026-10-28",
  "note": "First disbursement"
}
```

`POST /api/loans/{loan_reference}/repayments`
```json
{
  "external_reference": "REP-001",
  "amount": 500000,
  "payment_date": "2026-11-28",
  "note": "Partial repayment"
}
```

### Transactions & Reconciliation
`GET /api/transactions/{external_reference}`

`POST /api/reconciliation`
```json
{
  "from_date": "2026-10-01",
  "to_date": "2026-10-31",
  "references": ["DISB-001", "REP-001"]
}
```
Returns list of MATCHED / MISSING_IN_ERP / MISSING_IN_FINERACT / AMOUNT_MISMATCH.

## Idempotency Contract (Part F)
Every state-changing request must carry `external_reference`.

| Case                                      | Behaviour                                      |
|-------------------------------------------|------------------------------------------------|
| New reference                             | Process once                                   |
| Same reference + same payload + finished  | 200, original body                             |
| Same reference + same payload + in progress | 202 with current status                      |
| Same reference + different payload        | 409 Conflict                                   |

Scoped uniqueness:
- GL account: per `external_reference` (+ code unique)
- Client: per `external_reference`; `client_uid` unique at DB
- Loan application: per `external_reference`
- Disbursement: unique per loan (one successful disbursement)
- Repayment: per `external_reference` (many allowed per loan)

## Mock ERP API (port 8001)
- `POST /api/accounts` – chart of accounts (idempotent on external_reference)
- `GET /api/accounts`
- `GET /api/accounts/{code}/balance`
- `POST /api/journal-entries` – balanced entries only (idempotent)
- `GET /api/journal-entries/{external_reference}`