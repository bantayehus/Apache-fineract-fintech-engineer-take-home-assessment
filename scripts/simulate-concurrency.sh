#!/usr/bin/env bash
# Part I2 / I3 – concurrent disbursements and repayments
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib.sh"

EVIDENCE_DIR="$ROOT/evidence/concurrency-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$EVIDENCE_DIR"

print_section "I2. Concurrent disbursements (same loan)"

# Prepare a dedicated loan
api POST "/api/clients" -d '{
  "external_reference": "CLIENT-CONC-001",
  "client_uid": "SME-CONC-001",
  "firstname": "Conc",
  "lastname": "Client"
}' >/dev/null || true

api POST "/api/loans" -d '{
  "external_reference": "LOAN-CONC-001",
  "loan_reference": "LN-CONC-001",
  "client_uid": "SME-CONC-001",
  "principal": 2000000,
  "auto_approve": true
}' >/dev/null || true

print_section "I2a. 10 concurrent requests with THE SAME external_reference"
PIDS=()
for i in $(seq 1 10); do
  (
    api POST "/api/loans/LN-CONC-001/disburse" -d '{
      "external_reference": "DISB-CONC-SAME",
      "note": "Concurrent same-ref"
    }' > "$EVIDENCE_DIR/same-ref-$i.json" 2>&1 || true
  ) &
  PIDS+=($!)
done
for p in "${PIDS[@]}"; do wait "$p" || true; done

echo "Responses written to $EVIDENCE_DIR/same-ref-*.json"
grep -h '"status"' "$EVIDENCE_DIR"/same-ref-*.json 2>/dev/null | sort | uniq -c | tee "$EVIDENCE_DIR/same-ref-summary.txt" || true

print_section "I2b. 10 concurrent requests with DIFFERENT external_references"
PIDS=()
for i in $(seq 1 10); do
  (
    api POST "/api/loans/LN-CONC-001/disburse" -d "{
      \"external_reference\": \"DISB-CONC-DIFF-$i\",
      \"note\": \"Concurrent different-ref $i\"
    }" > "$EVIDENCE_DIR/diff-ref-$i.json" 2>&1 || true
  ) &
  PIDS+=($!)
done
for p in "${PIDS[@]}"; do wait "$p" || true; done

echo "Responses written to $EVIDENCE_DIR/diff-ref-*.json"
grep -h '"status"' "$EVIDENCE_DIR"/diff-ref-*.json 2>/dev/null | sort | uniq -c | tee "$EVIDENCE_DIR/diff-ref-summary.txt" || true

print_section "Expected: exactly ONE successful disbursement in both cases"
print_kv "Last line of defence" "DB unique constraint on (operation_type, external_reference) + Fineract loan state + integration unique-per-loan check"

print_section "I3. Concurrent repayments with different references"
# Use a second loan that is already disbursed if possible; otherwise skip gracefully
api POST "/api/loans" -d '{
  "external_reference": "LOAN-CONC-REP",
  "loan_reference": "LN-CONC-REP",
  "client_uid": "SME-CONC-001",
  "principal": 1000000,
  "auto_approve": true
}' >/dev/null || true

api POST "/api/loans/LN-CONC-REP/disburse" -d '{
  "external_reference": "DISB-CONC-REP",
  "note": "For repayment concurrency"
}' >/dev/null || true

PIDS=()
for i in $(seq 1 5); do
  (
    api POST "/api/loans/LN-CONC-REP/repayments" -d "{
      \"external_reference\": \"REP-CONC-$i\",
      \"amount\": 10000
    }" > "$EVIDENCE_DIR/repay-conc-$i.json" 2>&1 || true
  ) &
  PIDS+=($!)
done
for p in "${PIDS[@]}"; do wait "$p" || true; done

print_section "Concurrency simulation complete"
print_kv "Evidence" "$EVIDENCE_DIR"