.PHONY: up down seed wait simulate-core simulate-duplicates simulate-concurrency \
        simulate-failures simulate-reconciliation simulate-all test-python test-java help

up:
	docker compose up -d --build

down:
	docker compose down -v

wait:
	./scripts/wait-for-services.sh

seed: wait
	./scripts/seed-fineract.sh

simulate-core:
	./scripts/simulate-core.sh

simulate-duplicates:
	./scripts/simulate-duplicates.sh

simulate-concurrency:
	./scripts/simulate-concurrency.sh

simulate-failures:
	./scripts/simulate-failures.sh

simulate-reconciliation:
	./scripts/simulate-reconciliation.sh

simulate-all: simulate-core simulate-duplicates simulate-concurrency simulate-failures simulate-reconciliation

test-python:
	cd integration-service && python -m pytest -q --cov=app --cov-report=term-missing || true
	cd mock-erp && python -m pytest -q || true

test-java:
	./scripts/run-java-tests.sh

help:
	@echo "Targets:"
	@echo "  up / down              Start or stop the full stack"
	@echo "  wait                   Wait for health endpoints"
	@echo "  seed                   Seed Fineract (office, currency, product, GLs)"
	@echo "  simulate-core          Full loan lifecycle"
	@echo "  simulate-duplicates    Sequential duplicate disbursements"
	@echo "  simulate-concurrency   Parallel disbursements & repayments"
	@echo "  simulate-failures      Failure matrix documentation + live check"
	@echo "  simulate-reconciliation Reconciliation report"
	@echo "  simulate-all           Run every simulation"
	@echo "  test-python / test-java Run unit tests"