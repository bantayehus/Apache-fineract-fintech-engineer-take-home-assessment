#!/usr/bin/env bash
# Part K – reconciliation report
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib.sh"

EVIDENCE_DIR="$ROOT/evidence/reconciliation-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$EVIDENCE_DIR"

print_section "Part K – Reconciliation"

RESP=$(api POST "/api/reconciliation" -d '{
  "references": ["DISB-001", "REP-001", "REP-002", "REP-003", "REP-FINAL", "DISB-DUP-SAME"]
}')
echo "$RESP" | tee "$EVIDENCE_DIR/reconciliation-report.json"

print_section "Expected outcome categories"
print_kv "MATCHED" "Present in both Integration/Fineract and ERP with same external_reference"
print_kv "MISSING_IN_ERP" "In Fineract path but no ERP journal entry"
print_kv "MISSING_IN_FINERACT" "In ERP but not recorded in Integration"
print_kv "AMOUNT_MISMATCH" "Both present but amounts differ (or unable to match)"

print_section "Reconciliation simulation complete"
print_kv "Evidence" "$EVIDENCE_DIR"