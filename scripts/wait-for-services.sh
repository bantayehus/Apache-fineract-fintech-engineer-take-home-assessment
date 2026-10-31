#!/usr/bin/env bash
set -euo pipefail

echo "==> Waiting for services to become healthy..."

wait_http() {
  local url=$1
  local name=$2
  local max=${3:-60}
  local i=0
  until curl -sf "$url" >/dev/null 2>&1; do
    i=$((i + 1))
    if [[ $i -ge $max ]]; then
      echo "ERROR: $name did not become ready at $url"
      exit 1
    fi
    sleep 2
  done
  echo "  OK  $name"
}

wait_http "http://localhost:8001/health" "Mock ERP"
wait_http "http://localhost:8000/health" "Integration Service"
# Fineract can take longer on first boot
wait_http "http://localhost:8080/fineract-provider/actuator/health" "Fineract" 90

echo "==> All services ready"