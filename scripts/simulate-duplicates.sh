#!/usr/bin/env bash
# Part I1 – sequential duplicates of the same disbursement
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib.sh"

EVIDENCE_DIR="$ROOT/evidence/duplicates-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$EVIDENCE_DIR"

print_section "I1. Sequential duplicate disbursements"

# Ensure a loan exists (idempotent create)
api POST "/api/clients" -d '{
  "external_reference": "CLIENT-DUP-001",
  "client_uid": "SME-DUP-001",
  "firstname": "Dup",
  "lastname": "Client"
}' >/dev/null || true

api POST "/api/loans" -d '{
  "external_reference": "LOAN-DUP-001",
  "loan_reference": "LN-DUP-001",
  "client_uid": "SME-DUP-001",
  "principal": 1000000,
  "auto_approve": true
}' >/dev/null || true

print_section "Sending same disbursement 4 times (same external_reference)"
for i in 1 2 3 4; do
  RESP=$(api POST "/api/loans/LN-DUP-001/disburse" -d '{
    "external_reference": "DISB-DUP-SAME",
    "note": "Duplicate attempt"
  }')
  echo "Attempt $i: $RESP" | tee -a "$EVIDENCE_DIR/attempts.jsonl"
done

print_section "Expected vs Actual"
print_kv "Requests received" "4"
print_kv "Expected Fineract disbursements" "1"
print_kv "Expected ERP journal entries" "1"
print_kv "Expected Integration transactions" "1"

# Count completed DISBURSEMENT ops for this loan
COMPLETED=$(api GET "/api/transactions/DISB-DUP-SAME" || echo '{}')
echo "$COMPLETED" | tee "$EVIDENCE_DIR/final-transaction.json"

print_section "Duplicate simulation complete"
print_kv "Evidence" "$EVIDENCE_DIR"