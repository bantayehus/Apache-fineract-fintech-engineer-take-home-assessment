#!/usr/bin/env bash
# Part D / E – full loan lifecycle happy path
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib.sh
source "$ROOT/scripts/lib.sh"

EVIDENCE_DIR="$ROOT/evidence/core-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$EVIDENCE_DIR"

print_section "1. Initial state"
print_kv "Evidence dir" "$EVIDENCE_DIR"

print_section "2. Sync GL accounts"
for code_name in "1100:Bank:ASSET" "1200:Loan Receivable:ASSET" "4000:Interest Income:INCOME"; do
  IFS=: read -r code name type <<< "$code_name"
  RESP=$(api POST "/api/accounts/sync" -d "{
    \"external_reference\": \"GL-$code\",
    \"code\": \"$code\",
    \"name\": \"$name\",
    \"type\": \"$type\",
    \"currency\": \"RWF\"
  }")
  echo "$RESP" | tee "$EVIDENCE_DIR/gl-sync-$code.json"
done

print_section "3. Create client"
CLIENT_RESP=$(api POST "/api/clients" -d '{
  "external_reference": "CLIENT-CREATE-001",
  "client_uid": "SME-000001",
  "firstname": "Acme",
  "lastname": "Trading Ltd"
}')
echo "$CLIENT_RESP" | tee "$EVIDENCE_DIR/client-create.json"

print_section "4. Lookup client"
api GET "/api/clients/SME-000001" | tee "$EVIDENCE_DIR/client-get.json"

print_section "5. Loan application (auto-approve)"
LOAN_RESP=$(api POST "/api/loans" -d '{
  "external_reference": "LOAN-APP-001",
  "loan_reference": "LN-2026-000001",
  "client_uid": "SME-000001",
  "product": "SME Asset Finance",
  "principal": 5000000,
  "currency": "RWF",
  "term_months": 12,
  "interest_rate": 18.0,
  "auto_approve": true
}')
echo "$LOAN_RESP" | tee "$EVIDENCE_DIR/loan-create.json"

print_section "6. Disburse"
DISB_RESP=$(api POST "/api/loans/LN-2026-000001/disburse" -d '{
  "external_reference": "DISB-001",
  "note": "Initial disbursement"
}')
echo "$DISB_RESP" | tee "$EVIDENCE_DIR/disburse.json"

print_section "7. Partial repayments (3x) + final payoff"
for i in 1 2 3; do
  RESP=$(api POST "/api/loans/LN-2026-000001/repayments" -d "{
    \"external_reference\": \"REP-00$i\",
    \"amount\": 500000,
    \"note\": \"Partial repayment $i\"
  }")
  echo "$RESP" | tee "$EVIDENCE_DIR/repay-$i.json"
done

# Final larger payment to clear remaining balance (simplified)
FINAL=$(api POST "/api/loans/LN-2026-000001/repayments" -d '{
  "external_reference": "REP-FINAL",
  "amount": 4000000,
  "note": "Final payoff"
}')
echo "$FINAL" | tee "$EVIDENCE_DIR/repay-final.json"

print_section "8. Transaction lookups"
for ref in DISB-001 REP-001 REP-FINAL; do
  api GET "/api/transactions/$ref" | tee "$EVIDENCE_DIR/txn-$ref.json"
done

print_section "Core lifecycle simulation complete"
print_kv "Evidence written to" "$EVIDENCE_DIR"