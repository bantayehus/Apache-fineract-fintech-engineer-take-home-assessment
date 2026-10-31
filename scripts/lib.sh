#!/usr/bin/env bash
# Shared helpers for simulation scripts

INTEGRATION_URL="${INTEGRATION_URL:-http://localhost:8000}"
AUTH_TOKEN="${AUTH_TOKEN:-assessment-secret-token}"
AUTH_HEADER="Authorization: Bearer $AUTH_TOKEN"
CT="Content-Type: application/json"

corr() {
  echo "corr-$(date +%s)-$RANDOM"
}

api() {
  local method=$1 path=$2
  shift 2
  local cid
  cid=$(corr)
  curl -s -X "$method" "${INTEGRATION_URL}${path}" \
    -H "$AUTH_HEADER" \
    -H "$CT" \
    -H "X-Correlation-ID: $cid" \
    "$@"
}

print_section() {
  echo
  echo "============================================================"
  echo "  $1"
  echo "============================================================"
}

print_kv() {
  printf "  %-28s %s\n" "$1" "$2"
}