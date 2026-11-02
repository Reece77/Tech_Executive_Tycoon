# Root tasks. Recipes avoid shell-specific syntax so they run under sh and cmd.exe.

.PHONY: check check-fast playtest quickstart-saves check-ci-1 check-ci-2 balance nightly nightly-ci-1 nightly-ci-2 test-durations check-backend check-backend-fast check-frontend check-api dev gen-api golden fmt e2e

check: check-backend check-api check-frontend

# CI's two matrix jobs (.github/workflows/check.yml): together they are `make check` without the
# `nightly` tests (long statistical balance runs; .github/workflows/nightly.yml runs them). Backend
# tests are split by measured duration (tests/durations.json; refresh with `make test-durations`).
check-ci-1:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q -n auto -m "not nightly" --shard 1/2

check-ci-2: check-api check-frontend
	cd backend && uv run pytest -q -n auto -m "not nightly" --shard 2/2

# The balance runner (docs/balance-targets.md): 4 strategies x 10 seeds x 120 turns plus steady on
# easy and hard, one table of targets. Exits 1 if a pass/fail target (T1-T3) fails.
balance:
	uv run --project backend python tools/balance_runner.py

# The long statistical tests, including the balance targets in full (CI: nightly).
nightly:
	cd backend && uv run pytest -q -n auto -m nightly -s

# CI's nightly matrix (M10d): the nightly tests in two shards balanced by tests/durations.json.
nightly-ci-%:
	cd backend && uv run pytest -q -n auto -m nightly -s --shard $*/2

test-durations:
	cd backend && uv run pytest -q -n auto --store-durations --durations=20

# Everything except the golden tests, for local iteration. `make check` (and CI) runs them all.
check-fast: check-backend-fast check-api check-frontend

check-backend:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q -n auto

check-backend-fast:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q -n auto --ignore=tests/golden

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

# The M7c agent playtest: a new game played for 120 months through the browser (out of `make e2e`).
playtest:
	cd frontend && pnpm exec playwright test -c playwright.playtest.config.ts

# Quick-start saves for playtests (M7c): steady at turn 36 and blitzscale at its first month of stage 3.
quickstart-saves:
	uv run --project backend python tools/quickstart_saves.py
