# Step-by-step testing guide

## Prerequisites

- Docker + Docker Compose
- ≥ 8 GB RAM for building the custom Fineract image
- `curl` and optionally `jq`
- Postman (optional) – import `postman/Inkomoko-Fineract-Assessment.postman_collection.json`

---

## 1. Get the source

The full project lives at:

```
fintech-fineract-assessment/
├── README.md, ARCHITECTURE.md, API.md, DECISIONS.md, SIMULATIONS.md, TESTING.md
├── docker-compose.yml
├── Makefile
├── fineract-customization/     # Java Part A (Liquibase, patch, tests, Dockerfile)
├── integration-service/        # FastAPI Integration Service (full source)
├── mock-erp/                   # FastAPI Mock ERP (full source)
├── scripts/                    # seed + simulate-*.sh
├── postman/                    # Postman collection
└── evidence/                   # simulation outputs land here
```

Copy or zip this entire directory to your machine.

---

## 2. Build the custom Fineract image (Part A)

```bash
cd fintech-fineract-assessment/fineract-customization

docker build \
  --build-arg FINERACT_TAG=1.15.0 \
  -t fineract-custom:1.15.0-assessment \
  .
```

See `fineract-customization/BUILD.md` for local Gradle alternative.

**If the build is too heavy for a first pass**, you can temporarily point `docker-compose.yml` at the official image (`apache/fineract:latest`) to test the Python services only. Part A still requires the custom image for the final submission.

---

## 3. Start the stack

```bash
cd fintech-fineract-assessment

# Start everything
docker compose up -d --build

# Wait until healthy
bash scripts/wait-for-services.sh
# Expected:
#   OK  Mock ERP
#   OK  Integration Service
#   OK  Fineract
```

Check:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8001/health
curl -s http://localhost:8080/fineract-provider/actuator/health
```

---

## 4. Seed Fineract

```bash
bash scripts/seed-fineract.sh
```

This creates:

- Currency RWF  
- Office “Kigali Main Office”  
- GL accounts 1100 / 1200 / 4000 / 2100  
- Loan product “SME Asset Finance” (cash-based, 18 %, 12 months)

---

## 5. Run unit tests

```bash
# Python
cd integration-service && pip install -r requirements.txt && pytest -q
cd ../mock-erp && pip install -r requirements.txt && pytest -q

# Java (after patch is applied to a Fineract checkout)
bash scripts/run-java-tests.sh
```

---

## 6. Happy-path test (manual or Postman)

### 6.1 Auth header used everywhere

```
Authorization: Bearer assessment-secret-token
X-Correlation-ID: <any unique string>
Content-Type: application/json
```

### 6.2 Sync GL accounts

```bash
curl -s -X POST http://localhost:8000/api/accounts/sync \
  -H "Authorization: Bearer assessment-secret-token" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-gl-1200" \
  -d '{
    "external_reference": "GL-1200",
    "code": "1200",
    "name": "Loan Receivable",
    "type": "ASSET",
    "currency": "RWF"
  }' | jq .
```

Repeat for `GL-1100` (Bank, ASSET) and `GL-4000` (Interest Income, INCOME).

**Idempotency check:** send the same body again → same response, no duplicate.

### 6.3 Create client

```bash
curl -s -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer assessment-secret-token" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-client-001" \
  -d '{
    "external_reference": "CLIENT-CREATE-001",
    "client_uid": "SME-000001",
    "firstname": "Acme",
    "lastname": "Trading Ltd"
  }' | jq .
```

```bash
curl -s http://localhost:8000/api/clients/SME-000001 \
  -H "Authorization: Bearer assessment-secret-token" | jq .
```

### 6.4 Loan application → disburse → repay

```bash
# Application (auto-approve)
curl -s -X POST http://localhost:8000/api/loans \
  -H "Authorization: Bearer assessment-secret-token" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-loan-app" \
  -d '{
    "external_reference": "LOAN-APP-001",
    "loan_reference": "LN-2026-000001",
    "client_uid": "SME-000001",
    "principal": 5000000,
    "term_months": 12,
    "interest_rate": 18.0,
    "auto_approve": true
  }' | jq .

# Disburse
curl -s -X POST http://localhost:8000/api/loans/LN-2026-000001/disburse \
  -H "Authorization: Bearer assessment-secret-token" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-disb-001" \
  -d '{"external_reference": "DISB-001", "note": "Initial disbursement"}' | jq .

# Three partial repayments + final
for ref in REP-001 REP-002 REP-003; do
  curl -s -X POST http://localhost:8000/api/loans/LN-2026-000001/repayments \
    -H "Authorization: Bearer assessment-secret-token" \
    -H "Content-Type: application/json" \
    -H "X-Correlation-ID: corr-$ref" \
    -d "{\"external_reference\": \"$ref\", \"amount\": 500000}" | jq .
done

curl -s -X POST http://localhost:8000/api/loans/LN-2026-000001/repayments \
  -H "Authorization: Bearer assessment-secret-token" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: corr-rep-final" \
  -d '{"external_reference": "REP-FINAL", "amount": 4000000}' | jq .
```

### 6.5 Transaction lookup & reconciliation

```bash
curl -s http://localhost:8000/api/transactions/DISB-001 \
  -H "Authorization: Bearer assessment-secret-token" | jq .

curl -s -X POST http://localhost:8000/api/reconciliation \
  -H "Authorization: Bearer assessment-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"references": ["DISB-001", "REP-001", "REP-002", "REP-003", "REP-FINAL"]}' | jq .
```

---

## 7. Automated simulations (preferred evidence)

```bash
make simulate-core              # full lifecycle → evidence/core-*/
make simulate-duplicates        # I1 sequential duplicates
make simulate-concurrency       # I2 / I3 parallel tests
make simulate-failures          # Part J matrix
make simulate-reconciliation    # Part K report
# or
make simulate-all
```

Inspect JSON under `evidence/`.

---

## 8. Postman

1. Open Postman → Import → `postman/Inkomoko-Fineract-Assessment.postman_collection.json`
2. Collection variables:
   - `integration_url` = `http://localhost:8000`
   - `erp_url` = `http://localhost:8001`
   - `auth_token` = `assessment-secret-token`
3. Run folders in order: Health → GL Account Sync → Clients → Loans → Transactions & Reconciliation

---

## 9. What “good” looks like

| Check | Pass criteria |
|-------|----------------|
| GL sync × 2 identical | Same `fineract_gl_id`, status SYNCED |
| Client create × 2 same ref | Same client, no second row |
| Disburse × 4 same ref | Exactly 1 Fineract disbursement, 1 ERP journal, 1 Integration op |
| Concurrent disburse (same/different ref) | Exactly 1 disbursement |
| Reconciliation | MATCHED for completed refs; clear MISSING_* when forced |
| Logs | Structured JSON with `correlation_id`, `external_reference`, `status` |
| No Fineract numeric IDs in public API | Only `client_uid`, `loan_reference`, `external_reference` |

---

## 10. Troubleshooting

| Symptom | Action |
|---------|--------|
| Fineract health never OK | First boot can take 2–3 min; check `docker compose logs fineract` |
| 401 on Integration | Header must be `Authorization: Bearer assessment-secret-token` |
| 502 on loan/disburse | Fineract not seeded or productId mismatch – re-run `seed-fineract.sh` |
| Python tests fail on import | `pip install -r requirements.txt` inside each service directory |
| Custom image build OOM | Increase Docker memory to 6–8 GB; see BUILD.md |

---

## 11. Submission checklist

- [ ] Custom Fineract image builds and starts
- [ ] Java unit test for Part A passes
- [ ] `make simulate-all` produces evidence folders
- [ ] README states tiers completed and pinned versions
- [ ] DECISIONS.md covers customisation choice, idempotency, retries
- [ ] No Fineract internal IDs exposed as primary identifiers
- [ ] Git history has incremental commits (not one giant commit)
