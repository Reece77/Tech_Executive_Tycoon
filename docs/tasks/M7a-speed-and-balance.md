# M7a: Turn speed, balance runner and the balance pass

**Goal:** turns are fast enough for a 10-year game; a headless runner plays the v1 strategies over 10 seeds and 120 turns and checks `docs/balance-targets.md`; about 20 new event templates (several for a solo founder with no product); and a balance pass that meets the targets, including M6's two known event issues. First half of M7 (Reece, D1a); M7b (History screen, saves manager, tooltips and saved column views, "Ask my COO") follows as its own milestone.

**Spec sections:** §16, §17 (M7) · **ADRs:** 0002, 0005, 0008 · **Formulas:** `docs/formulas.md` §14.3, §15.7, §16 · **Depends on:** M6 (`m6-done`)

## Context

Reece's decisions (2026-10-30): D1a (M7a then M7b, merged separately); D2a ("Ask my COO" in M7b, built last and cut first); D3a (v1 strategies only: bootstrap-frugal, blitzscale, steady, do-nothing); D4a (a `nightly` pytest marker, a nightly workflow and `make balance` for the 120-turn runs; a 24-turn smoke version in PR CI); D5: tag pushes from cloud sessions are blocked (HTTP 403 from the session's git connection, not a GitHub setting), so a workflow does the tagging: `.github/workflows/tag-milestone.yml` runs when `check` succeeds on `main` and creates the tag named by a `Milestone-Tag: mX-done` trailer on the head commit (sub-task 2). Additions: the balance pass fixes M6's known issues (event morale within ±3 on seed 4; a solo founder with no product gets a varied early game, with some new templates aimed at that phase); `docs/balance-targets.md` is drafted first and approved by Reece before the runner is built against it. Rules kept from M6: speed work first; refresh `tests/durations.json` after each sub-task; add a third CI shard if any job passes 17 minutes.

## Out of scope

Everything in M7b. Research-heavy, acquirer and vertical-integrator strategies (v2/v3 systems). Sandbox mode. New game systems: the balance pass tunes `balance.yaml` keys and adds templates, nothing else.

## Sub-tasks (commit after each)

0. **Turn speed:** profile a persisted turn, then optimize. Target: turn 120 of the product-perf save under 300 ms locally. Golden snapshots unchanged.
1. **Balance targets:** draft `docs/balance-targets.md` (strategies, outcome measure, pass/fail targets, curves, event and speed bands). **Stop for Reece's approval.** (Approved 2026-10-30 with three changes, recorded in the file.)
2. **Strategies and runner:** the four strategies as scripts over the pure sim (`tst/balance/`, outside `tst/sim`; hiring through the real actions); `tools/balance_runner.py` (strategies, seeds, turns, difficulty; prints a table per target; exit code 1 on a failed pass/fail target); `make balance`; `tests/balance/test_balance_targets.py` marked `nightly` (the full run) and a 24-turn smoke test (2 seeds, every strategy finishes, no exception, ledger balanced) in PR CI; the long statistical tests move to `nightly`; PR CI shards run `-m "not nightly"`; `.github/workflows/nightly.yml` runs `make balance` and the `nightly` tests every night and on demand. `make check` still runs everything. `.github/workflows/tag-milestone.yml` tags milestone merges (D5); CLAUDE.md §6 step 2 says so.
3. **Templates:** about 20 more templates (personnel, operations, market), at least 6 of them for a solo founder or a company with no live product; validated at load like the others.
4. **Balance pass:** run the runner, tune only `balance.yaml` keys (and the new templates' weights) until every target is met; fix E2 (seed 4 morale) and E3 (solo-founder variety); record values in `docs/balance-targets.md` and the "Decisions made" below. Golden snapshots regenerated only if tuning changes them (CHANGELOG reason).
5. **Close-out:** durations, CI shard times (third shard if a job passes 17 minutes), CHANGELOG, data dictionary if any schema changed.

## Acceptance criteria

- [ ] Turn 120 of the product-perf save under 300 ms locally (before and after recorded).
- [ ] `docs/balance-targets.md` approved by Reece before sub-task 2.
- [ ] `make balance` plays 4 strategies × 10 seeds × 120 turns and prints every target with its value; T1–T3 pass; every band met or brought back to Reece.
- [ ] do-nothing fails on 10/10 seeds; no strategy wins more than 6/10.
- [ ] Event morale within ±3 on every seed; solo-founder early game meets E3.
- [ ] About 20 new templates, validated at load.
- [ ] Nightly workflow runs green; the PR smoke test runs in CI; each PR shard under 17 minutes or a third shard added.
- [ ] `make check` green; `make e2e` passes; merged with a `Milestone-Tag: m7a-done` trailer and tagged by the workflow per CLAUDE.md §6.

## Manual check (Reece, after merge)

Run `make balance` and read the table. Start a solo-founder game and play 12 months without a product: do the events feel varied?

## Decisions made

- **Sub-task 0 (turn speed).** Profiled turns 100–120 of the product-perf save: writes 70 ms, sim 54 ms (people updates 35), event writing 24, ledger sums 21. Changes: a save's SQLAlchemy engine is kept between sessions (`tst.db.session.shared_engine`, 16 most recent saves; NullPool still closes the file after each session), because a new engine per session threw away the compiled-SQL cache and recompiled every statement every turn; the ledger balances are remembered with the state after each turn and action (`current_balances`; `TST_STATE_CACHE_CHECK=1` compares them with a fresh sum), because summing the whole ledger grows with every month; row updates are Core executemany statements (reveal records batched across people) instead of the ORM's bulk update; ledger entries and lines, morale log, product months, snapshots, log and inbox rows are inserted with one executemany per table; growth reads skills once per person. RNG stream construction (14 µs, about 6 ms a turn) is left as is: a faster derivation would change every draw. **Result:** 120 persisted turns average 131 ms (266 before); turns 110–120 131 ms (215 before); the earn-and-burn pure-sim turn 45 ms (52). Local suite 7m12s with `-n auto` on 4 cores; the slowest tests are pure-sim statistics (judgment 146 s, event balance 96 s, offers 76 s, delegates 75 s), which sub-task 2 moves to `nightly`.

## Follow-ups

_(Agent fills in.)_
