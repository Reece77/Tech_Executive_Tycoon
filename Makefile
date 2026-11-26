# Root tasks. Recipes avoid shell-specific syntax so they run under sh and cmd.exe.

.PHONY: weekly-v4-a weekly-v4-b weekly-v4-c weekly-v4-systems weekly-m43-a1 weekly-m43-a2 weekly-m43-b1 weekly-m43-b2 weekly-m43-c1 weekly-m43-c2 weekly-m43-d1 weekly-m43-d2 weekly-m43-d3 weekly-m43-d4 weekly-m43-t6 weekly-v1 weekly-v5 weekly-v6 weekly-v3-shocks weekly-v3-integration weekly-v3-long weekly-v6-integrator weekly-m37 weekly-m45 weekly-m52 weekly-m27b check-timing check check-fast playtest quickstart-saves check-ci-1 check-ci-2 balance nightly nightly-ci test-durations check-backend check-backend-fast check-frontend check-api dev gen-api golden fmt e2e record-fixture weekly-v2-table m46-lift m46-board-trace

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

# CI's nightly matrix (M10d; six shards from M46): shard SHARD of NIGHTLY_SHARDS, balanced by
# tests/durations.json. Each shard prints every test's duration (--durations=0), the numbers
# tools/nightly_durations.py merges into the durations file to rebalance the shards.
NIGHTLY_SHARDS ?= 6
nightly-ci:
	cd backend && uv run pytest -q -n auto -m "nightly and not weekly" -s --durations=0 --shard $(SHARD)/$(NIGHTLY_SHARDS)

# The v2 30-year targets (M15a, formulas.md 30.7; CI: .github/workflows/weekly.yml, Sundays):
# V1 over 30 seeds, V5's runs to December 2039, and V6's turn time on a 2039 stage-4 save.
V6_SAVE_DIR ?= /tmp/tst-v6
weekly-v1to4:
	cd backend && uv run pytest -q -n auto -s -m weekly tests/balance/test_v2_balance.py::test_v1_to_v4_ten_years
# M46: V1-V4's ten-year table printed (the pytest test's table stays in its xdist worker)
weekly-v2-table:
	uv run --project backend python tools/v2_targets.py --runs
weekly-v1:
	uv run --project backend python tools/v2_targets.py --seeds-30
weekly-v5:
	uv run --project backend python tools/v2_targets.py --long --runs
weekly-v6:
	uv run --project backend python tools/v6_save.py $(V6_SAVE_DIR) v6
	cd backend && TST_V6_SAVE=$(V6_SAVE_DIR)/v6.tst.sqlite TST_M30_MEDIAN_MS=400 uv run pytest -q -n 0 -s -m weekly tests/integration/test_v6_perf.py tests/integration/test_m30_perf.py  # M30: 400 ms on this save's runner-adjusted median (M35a's ratio), restored by M45; the 1,000 ms raw budget stays

# M23b's v3 targets (tst.balance.v3; CI: weekly.yml): the chain's shocks, 20 years of the v2
# and v3 founder-played strategies (integration pays), the v3 scripts to December 2039, and V6
# extended on a 2039 full_integrator save.
weekly-v3-shocks:
	cd backend && uv run pytest -q -n 0 -s -m weekly tests/balance/test_v3_balance.py::test_v3_shocks
weekly-v3-integration:
	cd backend && uv run pytest -q -n 0 -s -m weekly tests/balance/test_v3_balance.py::test_v3_integration_thirty_years
weekly-v3-long:
	cd backend && uv run pytest -q -n 0 -s -m weekly tests/balance/test_v3_balance.py::test_v3_chain_thirty_years
weekly-m27b:
	cd backend && uv run pytest -q -n 0 -s -m weekly tests/balance/test_m27b_balance.py
weekly-v6-integrator:
	uv run --project backend python tools/v6_save.py $(V6_SAVE_DIR) v6i --strategy full_integrator
	cd backend && TST_V6_SAVE=$(V6_SAVE_DIR)/v6i.tst.sqlite TST_M30_MEDIAN_MS=400 uv run pytest -q -n 0 -s -m weekly tests/integration/test_v6_perf.py tests/integration/test_m30_perf.py  # M30: 400 ms on this save's runner-adjusted median (M35a's ratio), reached in M45; the 1,000 ms raw budget stays

# M46: re-record a long state fixture on CI and print it to the log (tools/record_state_fixtures.py;
# FIXTURE m30, m32, m37 or m45). Dispatch weekly.yml with parts ["record-fixture FIXTURE=m30", ...].
record-fixture:
	uv run --project backend python tools/record_state_fixtures.py $(FIXTURE)

# M46: M27a's 40.10 targets and M46's target with balance overrides (SET=key=value,key=value),
# and the V6 save's board through 2042 (tools/m46_lift_sweep.py, tools/m46_board_trace.py)
m46-lift:
	uv run --project backend python tools/m46_lift_sweep.py $(SET)
m46-board-trace:
	uv run --project backend python tools/m46_board_trace.py $(SET)

# M45 (sub-task 1): M37's dynasty game on seeds 1-3 for 720 months, every month's full-state
# digest against the one recorded before any M45 change (tests/fixtures/m45_dynasty_hashes.json).
weekly-m45:
	cd backend && uv run pytest -q -n 3 -s -m weekly tests/balance/test_m45_state_cache.py

# M37 (52.5 target 5): a full_integrator dynasty save with a family to January 2069 (708
# months), then its 2069 months against a 500 ms runner-adjusted median (M45) and the save under 400 MB.
weekly-m37:
	uv run --project backend python tools/v6_save.py $(V6_SAVE_DIR) m37 --strategy full_integrator --turns 708 --length dynasty --children 2,5
	cd backend && TST_M37_SAVE=$(V6_SAVE_DIR)/m37.tst.sqlite uv run pytest -q -n 0 -s -m weekly tests/integration/test_m37_perf.py

# M52 (66.4 target 4): M45's dynasty game continued in sandbox to December 2100 on seeds 1-3 (no
# error, every integer within int64, the 2100 economy 1,000x below it), then seed 1's save's 2101
# months against the 550 ms runner-adjusted dynasty guard.
weekly-m52:
	uv run --project backend python tools/m52_save.py $(V6_SAVE_DIR) m52
	cd backend && TST_M52_SAVE=$(V6_SAVE_DIR)/m52.tst.sqlite uv run pytest -q -n 0 -s -m weekly tests/integration/test_m52_perf.py

# M35b's v4 targets (tst.balance.v4; CI: weekly.yml): the four v4 scripts and every comparison
# played to December 2039, in three seed shards (each saves its runs: tools/v4_targets.py --load
# combines them), and T5's own targets of M31-M34 on the combined code.
V4_OUT ?= /tmp/tst-v4
weekly-v4-a:
	mkdir -p $(V4_OUT) && cd backend && TST_V4_SEEDS=1-10 TST_V4_SAVE=$(V4_OUT)/v4-1-10.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v4_balance.py
weekly-v4-b:
	mkdir -p $(V4_OUT) && cd backend && TST_V4_SEEDS=11-20 TST_V4_SAVE=$(V4_OUT)/v4-11-20.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v4_balance.py
weekly-v4-c:
	mkdir -p $(V4_OUT) && cd backend && TST_V4_SEEDS=21-30 TST_V4_SAVE=$(V4_OUT)/v4-21-30.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v4_balance.py
weekly-v4-systems:
	uv run --project backend python tools/m31_targets.py
	uv run --project backend python tools/m32_targets.py
	uv run --project backend python tools/m33_targets.py
	uv run --project backend python tools/m34_targets.py

# M43's v5 targets (tst.balance.v5; CI: weekly.yml): every strategy since v1 played to December
# 2039 in three seed shards, and the v5 strategies with a family to December 2069; each saves
# its runs (tools/v5_targets.py --load combines them).
V5_OUT ?= /tmp/tst-v5
# five seeds a 30-year job and two or three a dynasty job: a 10-seed shard ran past GitHub's
# job limit on the real-listings IPO floor (M43)
weekly-m43-a1:
	mkdir -p $(V5_OUT) && cd backend && TST_V5_SEEDS=1-5 TST_V5_SAVE=$(V5_OUT)/v5-1-5.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v5_balance.py
weekly-m43-a2:
	mkdir -p $(V5_OUT) && cd backend && TST_V5_SEEDS=6-10 TST_V5_SAVE=$(V5_OUT)/v5-6-10.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v5_balance.py
weekly-m43-b1:
	mkdir -p $(V5_OUT) && cd backend && TST_V5_SEEDS=11-15 TST_V5_SAVE=$(V5_OUT)/v5-11-15.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v5_balance.py
weekly-m43-b2:
	mkdir -p $(V5_OUT) && cd backend && TST_V5_SEEDS=16-20 TST_V5_SAVE=$(V5_OUT)/v5-16-20.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v5_balance.py
weekly-m43-c1:
	mkdir -p $(V5_OUT) && cd backend && TST_V5_SEEDS=21-25 TST_V5_SAVE=$(V5_OUT)/v5-21-25.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v5_balance.py
weekly-m43-c2:
	mkdir -p $(V5_OUT) && cd backend && TST_V5_SEEDS=26-30 TST_V5_SAVE=$(V5_OUT)/v5-26-30.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v5_balance.py
weekly-m43-d1:
	mkdir -p $(V5_OUT) && cd backend && TST_V5_SEEDS=1-3 TST_V5_DYNASTY=1 TST_V5_SAVE=$(V5_OUT)/v5-dynasty-1-3.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v5_balance.py
weekly-m43-d2:
	mkdir -p $(V5_OUT) && cd backend && TST_V5_SEEDS=4-6 TST_V5_DYNASTY=1 TST_V5_SAVE=$(V5_OUT)/v5-dynasty-4-6.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v5_balance.py
weekly-m43-d3:
	mkdir -p $(V5_OUT) && cd backend && TST_V5_SEEDS=7-8 TST_V5_DYNASTY=1 TST_V5_SAVE=$(V5_OUT)/v5-dynasty-7-8.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v5_balance.py
weekly-m43-d4:
	mkdir -p $(V5_OUT) && cd backend && TST_V5_SEEDS=9-10 TST_V5_DYNASTY=1 TST_V5_SAVE=$(V5_OUT)/v5-dynasty-9-10.json uv run pytest -q -n 0 -s -m weekly tests/balance/test_v5_balance.py

# M43 T3 and T6, on demand (weekly.yml's `parts` input): each v5 system's targets on the combined
# code (one tool a job), and 54.4's economy (technology's share of world GDP) to December 2069
WEEKLY_M43_T3 := m38 m39 m40 m41 m42 m44
$(addprefix weekly-m43-t3-,$(WEEKLY_M43_T3)):
	uv run --project backend python tools/$(patsubst weekly-m43-t3-%,%,$@)_targets.py
weekly-m43-t3-m36:  # reads Settings().data_dir, relative to backend/
	cd backend && uv run python ../tools/m36_targets.py
weekly-m43-t6:
	uv run --project backend python tools/m43a_targets.py

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
