# Design Decisions & Trade-offs

## 1. Fineract Customization Mechanism (Part A)
**Choice:** Liquibase migration + extension of the existing GL account create command path (domain service / command handler) rather than a completely separate REST resource that bypasses Fineract’s command pipeline.

**Rationale:**
- Guarantees the same permission checks, transaction boundaries and audit trail as native GL creation.
- The required behaviours (unique external_reference, identical-payload idempotency, conflict on different payload) belong inside Fineract’s own consistency boundary.
- A thin Java wrapper around the public API would not satisfy the assessment’s “real change inside Fineract” requirement.

**Known limitation:** The upstream GL account entity did not have an external reference field; we added one. Future upstream support for externalId on GL accounts would allow us to drop the custom column.

## 2. Sync Trigger
**Choice:** Explicit `POST /api/accounts/sync` on the Integration Service (plus optional polling helper). ERP can also call a webhook endpoint if desired.

**Rationale:** Deterministic, easy to test, no dependency on ERP webhook reliability for the assessment. Order is enforced by the Integration Service: GL accounts must be SYNCED before a loan product that references them is created.

## 3. Database Constraints vs Application Locks
**Choice:** Unique constraints in the Integration Service PostgreSQL database are the primary idempotency and concurrency guard. Application-level locks / SELECT FOR UPDATE are used as a secondary optimisation only.

**Rationale:** Under concurrent load or multi-instance deployment an in-memory lock or pure application check is insufficient. The last line of defence must be a durable unique index. Fineract’s own loan-state machine + externalId uniqueness provide an additional safety net for disbursements.

## 4. Timeout Handling
**Choice:** Never blindly retry a Fineract call after a timeout. Always look up by the external reference that was sent as Fineract’s externalId / transaction externalId.

**Rationale:** Classic “at-least-once” trap. Looking up first makes the operation safe to retry and prevents double posting.

## 5. Recovery Without a Worker
**Choice:** Persisted state machine + startup sweep + optional admin recovery endpoint. No Celery / Kafka required.

**Rationale:** Assessment explicitly allows this. Keeps the operational surface small while still guaranteeing that an interrupted “Fineract success → ERP call” can be completed after restart.

## 6. Accounting Basis
**Choice:** Cash-based accounting for the loan product (simpler, matches the suggested disbursement/repayment journal patterns, no receivable accounts needed for interest).

**Rationale:** Documented in seed scripts. Accrual would require additional GL accounts and more complex mapping; cash is sufficient for the required scenarios and keeps the demonstration clear.

## 7. What Was Deliberately Not Built
- Multi-tranche disbursements
- Fees / penalties / taxes (stretch)
- Full GL master-data reconciliation (stretch)
- Prometheus / OpenTelemetry (stretch)
- Signed partner webhooks (stretch)
- Message queue / outbox pattern (not required; state machine + recovery is enough)

## 8. Known Weaknesses
- The custom Fineract image must be rebuilt whenever the patch changes; this is expected.
- Recovery currently relies on a sweep; under extreme load a dedicated worker would be preferable in production.
- Concurrent repayments of the exact same amount with different references are safe, but very high concurrency on a single loan can still produce transient lock contention (observable, not correctness-breaking).
- The assessment environment starts Fineract with an empty database; all seed data is scripted and repeatable.

## Sample Log Trail – “What happened to FIN-2026-000001?”
```json
{"timestamp":"2026-10-28T12:01:03Z","correlation_id":"corr-9f3a…","external_reference":"FIN-2026-000001","loan_reference":"LN-2026-000001","status":"RECEIVED","msg":"Disbursement request accepted"}
{"timestamp":"2026-10-28T12:01:03Z","correlation_id":"corr-9f3a…","external_reference":"FIN-2026-000001","status":"FINERACT_PENDING"}
{"timestamp":"2026-10-28T12:01:04Z","correlation_id":"corr-9f3a…","external_reference":"FIN-2026-000001","fineract_transaction_id":"42","status":"FINERACT_DONE"}
{"timestamp":"2026-10-28T12:01:04Z","correlation_id":"corr-9f3a…","external_reference":"FIN-2026-000001","status":"ERP_PENDING"}
{"timestamp":"2026-10-28T12:01:05Z","correlation_id":"corr-9f3a…","external_reference":"FIN-2026-000001","erp_transaction_id":"JE-7781","status":"COMPLETED"}
```
One API call: `GET /api/transactions/FIN-2026-000001` returns the full state machine history + Fineract and ERP identifiers.