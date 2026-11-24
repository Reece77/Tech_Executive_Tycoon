# M51: Scenarios and challenges (v6, lane C)

**Goal:** reasons to start again. Six new scenarios join §30.3's five: the 2008 crash, a failing chipmaker, an EV maker, a Chinese foundry under controls, a platform war, and a dynasty. Challenge rules can be added to any game, each enforced by the engine and scored. A Scenarios screen keeps your best results across saves.

**Formulas:** `docs/formulas.md` §63 (all), with §30, §60 · **ADRs:** 0002, 0024 · **Depends on:** M50 (`m50-done`) · **Lane:** C, alongside M49 (lane A) and M53 (lane B)

## Reece's decision (2026-11-21)

- **Scenarios** are part of v6.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m51-scenarios` from `main`.
- **Must not edit** M49's or M53's's files. Merge `main` often.
- **CLAUDE.md §9's decision rules apply.**
- **M51 owns:** `scenarios.yaml`, `tst/sim/modes/` (scenario and challenge rules), the scenario and result screens, the app-wide results file, `challenges.*` keys, and `tst/balance/m51.py`.
- **Merges last** of this round.
- §63.4 target 3 (a normal game with no challenge rules plays exactly as before) is the guard.

## Sub-tasks (commit after each)

1. **The six scenarios** (§63.1) in `scenarios.yaml`, built with §30.2's world code (and M50's 2008 start for "The crash"). Each start and goal is checked with a scripted sensible player and a passive one on seeds 1–10. Adjust a goal or deadline to land in §63.4 target 1's band, and record each change.
2. **Challenge rules** (§63.2): each enforced as a refusal with a clear reason, with its score multiplier.
3. **The Scenarios screen and results** (§63.3): briefs, difficulty from seeds 1–10's win rates, best results and challenges kept in an app-wide results file (outside saves; it survives the M58 installer's updates), and the result screen's breakdown and comparison.
4. **API, e2e, balance and close-out:**
   - **Playwright:** (a) start "The crash" and fail it, (b) add the bootstrapped challenge and see a funding round refused, (c) a best result appears on the Scenarios screen;
   - **§63.4 targets** printed;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] All six new scenarios load, and each is winnable and losable as §63.4 target 1 says.
- [ ] Every challenge rule is enforced with a clear reason, and lowers the score as target 2 says.
- [ ] A normal game with no challenges plays exactly as before (state-cache check).
- [ ] `make check`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m51-done`.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
