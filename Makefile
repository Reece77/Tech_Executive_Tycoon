# Root tasks. Recipes avoid shell-specific syntax so they run under sh and cmd.exe.

.PHONY: check check-backend check-frontend check-api dev gen-api golden fmt e2e

check: check-backend check-api check-frontend

check-backend:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q

# Regenerates frontend/src/api and fails if the committed files differ (ADR-0009).
check-api:
	uv run --project backend python tools/check_generated.py

check-frontend:
	cd frontend && pnpm lint && pnpm typecheck && pnpm test

dev:
	uv run --project backend python tools/dev.py

gen-api:
	cd frontend && pnpm gen:api

golden:
	cd backend && uv run pytest tests/golden -q

fmt:
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && pnpm fmt

# Playwright smoke test; starts its own API and Vite servers on spare ports.
e2e:
	cd frontend && pnpm test:e2e
