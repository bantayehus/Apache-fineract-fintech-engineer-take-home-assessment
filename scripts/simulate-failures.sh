#!/usr/bin/env bash
# Part J – failure handling scenarios (documented behaviour; injection via env flags)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib.sh"

EVIDENCE_DIR="$ROOT/evidence/failures-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$EVIDENCE_DIR"

print_section "Part J – Failure scenarios (behaviour documentation + live checks)"

cat > "$EVIDENCE_DIR/failure-matrix.md" << 'EOF'
# Failure handling matrix

| # | Scenario | Status before | During | After recovery | Double-post prevented by |
|---|----------|---------------|--------|----------------|--------------------------|
| 1 | ERP down after Fineract success | FINERACT_DONE | ERP call fails → ERP_PENDING / NEEDS_RECONCILIATION | Startup sweep or admin recovery re-posts or marks for reconciliation | external_reference unique on ERP journal entry |
| 2 | Fineract down | RECEIVED / FINERACT_PENDING | Caller gets 502; operation persisted | Safe to retry after lookup | Operation row + unique constraint |
| 3 | Fineract timeout after send | FINERACT_PENDING | Unknown outcome | Lookup by externalId / external_reference; never blind retry | Lookup-before-retry |
| 4 | ERP timeout after write | ERP_PENDING | Unknown | Retry; ERP idempotent on external_reference → one journal entry | ERP unique constraint |
| 5 | Crash between Fineract success and ERP call | FINERACT_DONE | Process dies | Startup recovery_sweep moves to NEEDS_RECONCILIATION or re-drives ERP | Persisted state machine |

## State machine (allowed transitions)
RECEIVED → FINERACT_PENDING → FINERACT_DONE → ERP_PENDING → COMPLETED
Any step may go to FAILED or NEEDS_RECONCILIATION.
SAFE_TO_RETRY = {RECEIVED, FINERACT_PENDING (after lookup), ERP_PENDING, FAILED}

## Retry policy
- Max attempts: 5 (configurable)
- Backoff: exponential starting at 2s
- After max attempts → NEEDS_RECONCILIATION (manual or scheduled repair)
EOF

print_section "Live check: query a known transaction status"
api GET "/api/transactions/DISB-001" 2>/dev/null | tee "$EVIDENCE_DIR/sample-txn-status.json" || \
  echo '{"note":"No DISB-001 yet – run simulate-core first"}' | tee "$EVIDENCE_DIR/sample-txn-status.json"

print_section "Failure documentation written"
print_kv "Evidence" "$EVIDENCE_DIR/failure-matrix.md"