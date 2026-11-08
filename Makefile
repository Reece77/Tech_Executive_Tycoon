# Root tasks. Recipes avoid shell-specific syntax so they run under sh and cmd.exe.

.PHONY: weekly-v1 weekly-v5 weekly-v6 check-timing check check-fast playtest quickstart-saves check-ci-1 check-ci-2 balance nightly nightly-ci test-durations check-backend check-backend-fast check-frontend check-api dev gen-api golden fmt e2e

check: check-backend check-api check-frontend check-timing

# CI's two matrix jobs (.github/workflows/check.yml): together they are `make check` without the
# `nightly` tests (long statistical balance runs; .github/workflows/nightly.yml runs them). Backend
# tests are split by measured duration (tests/durations.json; refresh with `make test-durations`).
check-ci-1:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q -n auto -m "not nightly and not timing and not weekly" --shard 1/2

check-ci-2: check-api check-frontend
	cd backend && uv run pytest -q -n auto -m "not nightly and not timing and not weekly" --shard 2/2

# The turn-time budgets (marker `timing`, 1.0 s a turn): alone, without xdist, after the parallel
# suite, so they measure on an otherwise idle machine (M14, product manager 2026-11-06). CI runs
# this as its own step in shard 1 of `check`.
check-timing:
	cd backend && uv run pytest -q -n 0 -m "timing and not weekly"

# The balance runner (docs/balance-targets.md): 4 strategies x 10 seeds x 120 turns plus steady on
# easy and hard, one table of targets. Exits 1 if a pass/fail target (T1-T3) fails.
balance:
	uv run --project backend python tools/balance_runner.py

# The long statistical tests, including the balance targets in full (CI: nightly).
nightly:
	cd backend && uv run pytest -q -n auto -m "nightly and not weekly" -s

# CI's nightly matrix (M10d): shard SHARD of NIGHTLY_SHARDS, balanced by tests/durations.json.
NIGHTLY_SHARDS ?= 4
nightly-ci:
	cd backend && uv run pytest -q -n auto -m "nightly and not weekly" -s --shard $(SHARD)/$(NIGHTLY_SHARDS)

# The v2 30-year targets (M15a, formulas.md 30.7; CI: .github/workflows/weekly.yml, Sundays):
# V1 over 30 seeds, V5's runs to December 2039, and V6's turn time on a 2039 stage-4 save.
V6_SAVE_DIR ?= /tmp/tst-v6
weekly-v1to4:
	cd backend && uv run pytest -q -n auto -s -m weekly tests/balance/test_v2_balance.py::test_v1_to_v4_ten_years
weekly-v1:
	uv run --project backend python tools/v2_targets.py --seeds-30
weekly-v5:
	uv run --project backend python tools/v2_targets.py --long --runs
weekly-v6:
	uv run --project backend python tools/v6_save.py $(V6_SAVE_DIR) v6
	cd backend && TST_V6_SAVE=$(V6_SAVE_DIR)/v6.tst.sqlite uv run pytest -q -n 0 -s -m weekly tests/integration/test_v6_perf.py

test-durations:
	cd backend && uv run pytest -q -n auto --store-durations --durations=20

# Everything except the golden tests, for local iteration. `make check` (and CI) runs them all.
check-fast: check-backend-fast check-api check-frontend check-timing

check-backend:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q -n auto -m "not timing and not weekly"

check-backend-fast:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q -n auto -m "not timing and not weekly" --ignore=tests/golden

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
