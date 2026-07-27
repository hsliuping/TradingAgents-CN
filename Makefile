.PHONY: help install dev test test-pr009 type-check health readiness \
	init-dry-run init indexes-dry-run indexes backup-dry-run smoke \
	compose-up compose-down compose-logs compose-status safety-test

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
COMPOSE ?= docker compose

help:
	@echo "AlphaGuard MVP targets:"
	@echo "  make dev              Start FastAPI in safe local mode"
	@echo "  make test-pr009       Run PR-009 focused tests"
	@echo "  make readiness        Print honest runtime/data readiness"
	@echo "  make init-dry-run     Show safe initialization plan"
	@echo "  make indexes          Create missing indexes only"
	@echo "  make backup-dry-run   Show exact AlphaGuard backup scope"
	@echo "  make smoke            Run isolated MVP smoke test"

install:
	$(PYTHON) -m pip install -r requirements.txt
	cd frontend && npm ci

dev:
	ALPHAGUARD_SYSTEM_MODE=SIM_AUTONOMOUS ALPHAGUARD_LIVE_TRADING_ENABLED=false \
		$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	$(PYTHON) -m pytest -q

test-pr009:
	$(PYTHON) -m pytest -q tests/unit/alphaguard/test_operations_pr009.py \
		tests/unit/alphaguard/test_frontend_operations_contract_pr009.py \
		tests/integration/alphaguard/test_mvp_smoke_pr009.py

type-check:
	cd frontend && npm run type-check

health:
	curl --fail --silent http://localhost:8000/health/live

readiness:
	$(PYTHON) scripts/alphaguard_readiness_report.py

init-dry-run:
	$(PYTHON) scripts/alphaguard_initialize.py

init:
	$(PYTHON) scripts/alphaguard_initialize.py --execute

indexes-dry-run:
	$(PYTHON) scripts/init_alphaguard_operations_indexes.py

indexes:
	$(PYTHON) scripts/init_alphaguard_operations_indexes.py --execute

backup-dry-run:
	$(PYTHON) scripts/alphaguard_backup.py

smoke:
	$(PYTHON) scripts/alphaguard_mvp_smoke.py

compose-up:
	$(COMPOSE) up -d --build

compose-down:
	$(COMPOSE) down

compose-logs:
	$(COMPOSE) logs --tail=200

compose-status:
	$(COMPOSE) ps

safety-test:
	$(PYTHON) -m pytest -q tests/unit/test_alphaguard_baseline_guard.py
