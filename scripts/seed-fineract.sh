#!/usr/bin/env bash
# Seed a clean Fineract instance with the minimum configuration required by the assessment.
# Office: Kigali Main Office | Currency: RWF | Loan product: SME Asset Finance
# Run after: docker compose up -d && ./scripts/wait-for-services.sh
set -euo pipefail

FINERACT_URL="${FINERACT_URL:-http://localhost:8080/fineract-provider/api/v1}"
AUTH="mifos:password"
TENANT="default"
AUTH_HEADER="Authorization: Basic $(echo -n "$AUTH" | base64 -w0 2>/dev/null || echo -n "$AUTH" | base64)"
CT="Content-Type: application/json"
TID="Fineract-Platform-TenantId: $TENANT"

api() {
  local method=$1 path=$2
  shift 2
  curl -sf -X "$method" "$FINERACT_URL$path" \
    -H "$AUTH_HEADER" -H "$CT" -H "$TID" \
    "$@"
}

echo "==> Seeding Fineract at $FINERACT_URL"

# 1. Ensure RWF currency exists (may already be present)
echo "  - Currency RWF"
api POST "/currencies" -d '{
  "currencies": ["RWF"]
}' 2>/dev/null || true

# 2. Create / verify Head Office then Kigali Main Office
echo "  - Office: Kigali Main Office"
# Head office is usually id=1 after first boot. Create a child office if needed.
OFFICE_RESP=$(api POST "/offices" -d '{
  "name": "Kigali Main Office",
  "parentId": 1,
  "openingDate": "2020-01-01",
  "dateFormat": "yyyy-MM-dd",
  "locale": "en"
}' 2>/dev/null || echo '{}')
echo "    $OFFICE_RESP"

# 3. Create a least-privilege API user (optional – mifos/password works for assessment)
echo "  - API user (using default mifos for assessment simplicity)"

# 4. Create the GL accounts that the loan product will reference
#    These will also be synced via the Integration Service; we create them here
#    so the product can be configured immediately.
echo "  - Seed GL accounts (Bank, Loan Receivable, Interest Income)"

create_gl() {
  local name=$1 code=$2 type=$3
  api POST "/glaccounts" -d "{
    \"name\": \"$name\",
    \"glCode\": \"$code\",
    \"type\": $type,
    \"usage\": 1,
    \"manualEntriesAllowed\": true,
    \"externalReference\": \"GL-$code\"
  }" 2>/dev/null || echo "    (may already exist) $code"
}

create_gl "Bank" "1100" 1
create_gl "Loan Receivable" "1200" 1
create_gl "Interest Income" "4000" 4
create_gl "Suspense" "2100" 2

# Look up the GL account IDs we just created / that already exist
echo "  - Resolving GL account IDs"
GL_LIST=$(api GET "/glaccounts" || echo "[]")
# Simple extraction (requires jq if available; fallback to defaults)
if command -v jq >/dev/null 2>&1; then
  BANK_ID=$(echo "$GL_LIST" | jq -r '.[] | select(.glCode=="1100") | .id' | head -1)
  LOAN_ID=$(echo "$GL_LIST" | jq -r '.[] | select(.glCode=="1200") | .id' | head -1)
  INT_ID=$(echo "$GL_LIST" | jq -r '.[] | select(.glCode=="4000") | .id' | head -1)
  SUSP_ID=$(echo "$GL_LIST" | jq -r '.[] | select(.glCode=="2100") | .id' | head -1)
else
  BANK_ID=1; LOAN_ID=2; INT_ID=3; SUSP_ID=4
fi
echo "    Bank=$BANK_ID LoanReceivable=$LOAN_ID Interest=$INT_ID Suspense=$SUSP_ID"

# 5. Loan product: SME Asset Finance
#    Cash-based accounting, single disbursement, 18% annual, monthly, 12 months
echo "  - Loan product: SME Asset Finance"
PRODUCT_RESP=$(api POST "/loanproducts" -d "{
  \"name\": \"SME Asset Finance\",
  \"shortName\": \"SMEAF\",
  \"currencyCode\": \"RWF\",
  \"digitsAfterDecimal\": 0,
  \"inMultiplesOf\": 1,
  \"principal\": 5000000,
  \"minPrincipal\": 100000,
  \"maxPrincipal\": 50000000,
  \"numberOfRepayments\": 12,
  \"repaymentEvery\": 1,
  \"repaymentFrequencyType\": 2,
  \"interestRatePerPeriod\": 18,
  \"interestRateFrequencyType\": 3,
  \"amortizationType\": 1,
  \"interestType\": 0,
  \"interestCalculationPeriodType\": 1,
  \"transactionProcessingStrategyCode\": \"mifos-standard-strategy\",
  \"accountingRule\": 2,
  \"isInterestRecalculationEnabled\": false,
  \"fundSourceAccountId\": $BANK_ID,
  \"loanPortfolioAccountId\": $LOAN_ID,
  \"transfersInSuspenseAccountId\": $SUSP_ID,
  \"interestOnLoanAccountId\": $INT_ID,
  \"incomeFromFeeAccountId\": $INT_ID,
  \"incomeFromPenaltyAccountId\": $INT_ID,
  \"overpaymentLiabilityAccountId\": $SUSP_ID,
  \"writeOffAccountId\": $SUSP_ID,
  \"locale\": \"en\",
  \"dateFormat\": \"yyyy-MM-dd\"
}" 2>/dev/null || echo '{"message":"product may already exist"}')
echo "    $PRODUCT_RESP"

echo "==> Fineract seed complete"
echo "    Accounting rule: Cash-based (accountingRule=2) – chosen for clarity and"
echo "    because the required journal patterns (DR Loan Receivable / CR Bank) match cash."