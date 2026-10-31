# Simulations & Evidence

All simulations are scripted and re-runnable. Prefer:

```bash
make up
make seed
make simulate-all
```

Evidence is written under `evidence/<simulation>-<timestamp>/`.

Use the template below for each scenario.

---

## Evidence template (per simulation)

1. **Initial state**
2. **Request**
3. **Response**
4. **Fineract state**
5. **ERP state**
6. **Integration state**
7. **Expected result**
8. **Actual result**
9. **Explanation**

---

## 1. Core loan lifecycle (`make simulate-core`)

| Step | Description |
|------|-------------|
| GL sync | Sync 1100 Bank, 1200 Loan Receivable, 4000 Interest Income |
| Client | `SME-000001` / Acme Trading Ltd |
| Loan application | `LN-2026-000001`, 5 000 000 RWF, 18 %, 12 months, auto-approve |
| Disbursement | `DISB-001` |
| Repayments | Three × 500 000 + final payoff |
| Lookups | `/api/transactions/{ref}` after each stage |

**Expected:** Loan moves through application → approval → active → (repayments) → closed (obligations met) when balance is cleared. Every state-changing call carries a unique `external_reference`. Integration and ERP each record exactly one entry per reference.

**Evidence location:** `evidence/core-*/`

---

## 2. Sequential duplicates – I1 (`make simulate-duplicates`)

**Request:** Same disbursement (`DISB-DUP-SAME`) sent 4 times sequentially for loan `LN-DUP-001`.

| Metric | Expected | How verified |
|--------|----------|--------------|
| Requests received | 4 | Script loop |
| Fineract disbursements | 1 | Loan state / transaction list |
| ERP journal entries | 1 | `GET /api/journal-entries/DISB-DUP-SAME` |
| Integration transactions | 1 | `GET /api/transactions/DISB-DUP-SAME` → status COMPLETED, attempt_count ≥ 1 |

**Mechanism that prevents double processing:**  
DB unique constraint on `(operation_type, external_reference)` plus the application check that returns the original result when the operation is already COMPLETED. Fineract loan state provides an additional guard (a loan can be disbursed only once).

**Evidence location:** `evidence/duplicates-*/`

---

## 3. Concurrent disbursements – I2 (`make simulate-concurrency`)

### I2a – Same external_reference (10 parallel requests)
**Expected:** Exactly one successful disbursement. Remaining requests receive the original result or a conflict/already-disbursed response.

### I2b – Different external_references (10 parallel requests)
**Expected:** Still exactly one Fineract disbursement (unique-per-loan rule). Extra references are rejected with 409 ALREADY_DISBURSED.

**Layers relied upon (and why one alone is insufficient):**

| Layer | Role | Why not enough alone |
|-------|------|----------------------|
| API idempotency (application check) | Fast path for identical in-flight/completed refs | Race window under concurrency |
| Integration DB unique constraint | Serialises inserts for the same (type, ref) | Does not cover different refs for same loan |
| Integration unique-per-loan check | Blocks second DISBURSEMENT for the same loan_reference | Still needs Fineract as final authority |
| Fineract loan state + externalId | Last line of defence – loan can transition to “disbursed” only once | Must be combined with Integration uniqueness for clean API responses |

**Evidence location:** `evidence/concurrency-*/same-ref-summary.txt`, `diff-ref-summary.txt`

---

## 4. Concurrent repayments – I3

Multiple simultaneous repayments with **different** external_references.  
**Expected:** Each reference applies exactly once. Final Fineract outstanding balance equals initial outstanding minus the sum of principal/interest portions **as recorded by Fineract**, not merely the amounts the test sent. Duplicates of one reference apply only once.

**Evidence location:** `evidence/concurrency-*/repay-conc-*.json`

---

## 5. Failure handling – Part J (`make simulate-failures`)

Documented in `evidence/failures-*/failure-matrix.md`.

Key principles demonstrated by the design:

1. **ERP down after Fineract success** → operation left in `FINERACT_DONE` / `ERP_PENDING`; recovery sweep or explicit re-drive; ERP unique on `external_reference` prevents double journal.
2. **Fineract down** → 502 to caller; operation row persisted; safe to retry after service recovery.
3. **Fineract timeout after send** → never blind retry; look up by the external reference that was sent as Fineract `externalId`.
4. **ERP timeout after write** → retry is safe because ERP journal create is idempotent on `external_reference`.
5. **Crash between Fineract success and ERP call** → on restart, `recovery_sweep()` finds `FINERACT_DONE` / `ERP_PENDING` rows and moves them to `NEEDS_RECONCILIATION` (or re-drives).

---

## 6. Reconciliation – Part K (`make simulate-reconciliation`)

`POST /api/reconciliation` compares Integration operations (DISBURSEMENT / REPAYMENT) with ERP journal entries keyed by `external_reference`.

| Status | Meaning |
|--------|---------|
| MATCHED | Present in both |
| MISSING_IN_ERP | In Fineract path, not in ERP |
| MISSING_IN_FINERACT | In ERP, not in Integration/Fineract |
| AMOUNT_MISMATCH | Both present but amounts differ (or unable to match) |

Reconciliation is read-only by default. Any repair must be an explicit, idempotent action.

**Evidence location:** `evidence/reconciliation-*/reconciliation-report.json`

---

## How an engineer answers “What happened to FIN-2026-000001?”

1. `GET /api/transactions/FIN-2026-000001` → full state-machine history, Fineract & ERP IDs.
2. Grep structured logs for `"external_reference":"FIN-2026-000001"` (or the correlation_id returned by the API).

Sample log trail is shown in `DECISIONS.md`.