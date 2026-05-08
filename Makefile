# HAWKEYE — Makefile
# All targets run from the repo root. Target a fresh laptop with Docker.

COMPOSE        ?= docker compose
COMPOSE_PROD   ?= docker compose -f docker-compose.yml -f docker-compose.prod.yml
BACKEND_EXEC   = $(COMPOSE) exec -T backend

.PHONY: help up up-prod down logs ps seed replay replay-stop preflight test fmt lint deploy migrate shell-backend shell-frontend clean

help:
	@echo "HAWKEYE — common targets"
	@echo "  make up            Build + start full stack (dev compose)"
	@echo "  make up-prod       Build + start with prod overrides (binds admin to 127.0.0.1)"
	@echo "  make down          Stop the stack"
	@echo "  make logs          Tail backend logs"
	@echo "  make seed          Seed Postgres + Neo4j + Redis from synthetic data"
	@echo "  make replay        Start mule_burst replay (events flow → alerts fire)"
	@echo "  make replay-stop   Stop the replay producer"
	@echo "  make preflight     Run app/scripts/preflight_check.py inside backend"
	@echo "  make test          Backend pytest + frontend vitest"
	@echo "  make fmt           ruff format + prettier"
	@echo "  make lint          ruff check + mypy + tsc"
	@echo "  make migrate       alembic upgrade head"
	@echo "  make deploy        Push to main (CI/CD picks up)"

up:
	$(COMPOSE) up -d --build
	@echo ""
	@echo "Waiting for backend healthz..."
	@for i in $$(seq 1 60); do \
	  curl -sf http://localhost:8000/healthz >/dev/null 2>&1 && break; \
	  sleep 2; \
	done
	@echo "Backend is up. Run: make seed && make replay"

up-prod:
	$(COMPOSE_PROD) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f backend

ps:
	$(COMPOSE) ps

migrate:
	$(BACKEND_EXEC) alembic upgrade head

seed: migrate
	$(BACKEND_EXEC) python -m app.scripts.seed

replay:
	@curl -sf -X POST http://localhost:8000/replay/start \
	  -H "Content-Type: application/json" \
	  -d '{"mode":"mule_burst","rate":500}'
	@echo ""
	@echo "Replay started. Watch alerts: docker compose logs -f backend | grep ALERT"

replay-stop:
	@curl -sf -X POST http://localhost:8000/replay/stop
	@echo ""

preflight:
	$(BACKEND_EXEC) python -m app.scripts.preflight_check

test:
	$(BACKEND_EXEC) pytest -q
	cd frontend && npm test -- --run

fmt:
	$(BACKEND_EXEC) ruff format app/
	cd frontend && npm run format

lint:
	$(BACKEND_EXEC) ruff check app/
	$(BACKEND_EXEC) mypy app/
	cd frontend && npm run lint && npx tsc --noEmit

shell-backend:
	$(BACKEND_EXEC) bash

shell-frontend:
	$(COMPOSE) exec frontend sh

deploy:
	@echo "Pushing to main — GitHub Actions will run /opt/hawkeye/deploy/deploy.sh on the VPS."
	git push origin main

clean:
	$(COMPOSE) down -v --remove-orphans
	rm -rf backend/__pycache__ backend/.pytest_cache frontend/dist frontend/node_modules
