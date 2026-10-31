# Architecture

## Components

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  Financing      │     │  Integration Service │     │  Apache Fineract    │
│  Partner        │────▶│  (FastAPI / Python)  │────▶│  (customized)       │
│  (external)     │     │                      │     │  Java / Spring Boot │
└─────────────────┘     │  - Idempotency       │     │  - GL external_ref  │
                        │  - State machine     │     │  - Loan lifecycle   │
                        │  - Correlation IDs   │     └─────────────────────┘
                        │  - Recovery          │               │
                        └──────────┬───────────┘               │
                                   │                           │
                                   ▼                           │
                        ┌──────────────────────┐               │
                        │  Mock ERP            │◀──────────────┘
                        │  (FastAPI / Python)  │   (journal entries derived
                        │  - Chart of accounts │    from Fineract txns)
                        │  - Journal entries   │
                        └──────────────────────┘
```

## Data Flow (happy path)

1. **GL Sync**  
   ERP `POST /api/accounts` → Integration Service receives (webhook / explicit sync) →  
   calls customized Fineract GL endpoint with `external_reference` →  
   Fineract persists (or returns existing on identical payload).  
   Status: `SYNC_PENDING` → `SYNCED` / `FAILED`.

2. **Client**  
   Partner → Integration `POST /api/clients` (with `client_uid` + `external_reference`) →  
   Fineract client created with `externalId = client_uid`. Local mapping table stores the link.

3. **Loan Application → Approval → Disbursement → Repayments**  
   All state-changing calls carry a unique `external_reference`.  
   Integration Service persists an explicit state-machine record before calling Fineract.  
   After Fineract success, derives balanced journal entry from Fineract’s transaction breakdown and posts to ERP (idempotent on same `external_reference`).

4. **Reconciliation**  
   `POST /api/reconciliation` compares Fineract transactions vs ERP journal entries keyed by `external_reference`.

## Key Design Choices

### Fineract Customization (Part A)
- **Mechanism**: Liquibase migration adds `external_reference VARCHAR(100) UNIQUE` to `acc_gl_account`.  
  Extended the existing GL account create command handler (or added a thin dedicated endpoint that re-uses the same domain service) so that:
  1. `external_reference` is persisted and unique.
  2. Identical payload + same reference → return existing account (idempotent).
  3. Same reference + different payload → 409 Conflict.
  4. Protected by Fineract’s permission model (`CREATE_GLACCOUNT` / equivalent).
- Why this approach: keeps the change inside Fineract’s transaction boundary and permission system; avoids a parallel “shadow” table that could drift.

### Identities
- Public contract uses only business identifiers:
  - `client_uid` → stored as Fineract `client.externalId`
  - `loan_reference` → stored as Fineract `loan.externalId`
- Integration Service maintains a local mapping table; numeric Fineract IDs are never exposed.

### Idempotency & Concurrency
- Every state-changing operation is recorded in the Integration DB with a unique constraint on `(operation_type, external_reference)`.
- Disbursement uniqueness is additionally enforced per loan (Fineract loan state + integration unique constraint on loan_reference for the DISBURSE operation).
- Last line of defence for concurrent disbursements: Fineract’s own loan-state machine + the unique externalId on the loan transaction / integration DB unique index. Application-level locking alone is insufficient under multi-instance deployment; the DB constraint is the final guard.

### Failure / Recovery State Machine
```
RECEIVED
  → FINERACT_PENDING
      → FINERACT_DONE
          → ERP_PENDING
              → COMPLETED
  → FAILED
  → NEEDS_RECONCILIATION
```
- Persisted in Integration DB.
- On restart / scheduled sweep / admin endpoint: any `FINERACT_DONE` + `ERP_PENDING` (or timed-out) records are retried or moved to reconciliation.
- Timeouts after sending to Fineract are resolved by lookup using the external reference (never blind retry).

### Accounting Mapping (Part H)
Pure function that takes a Fineract loan transaction (with principal/interest breakdown) and produces balanced journal lines:
- Disbursement: DR Loan Receivable / CR Bank
- Repayment: DR Bank / CR Loan Receivable (principal) / CR Interest Income (interest)
Derived exclusively from Fineract’s transaction data; never recalculated independently.

## Technology Justification
- **FastAPI**: native async, automatic OpenAPI, excellent Pydantic validation, type-checker friendly.
- **PostgreSQL**: strong unique constraints, JSONB for flexible payloads if needed, mature for financial workloads.
- No message queue required for the reliability tier; persisted state + explicit recovery is sufficient and simpler to reason about.