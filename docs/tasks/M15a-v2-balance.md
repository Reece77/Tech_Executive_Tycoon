# M15a: v2 balance and long campaigns (lane A)

**Goal:** close v2's balance. Nine scripted strategies, including the new research-heavy, acquirer, partial-integrator and CEO-led ones, split the wins. Research is strong but not dominant. 30-year campaigns stay alive to 2039 with five more eras, and a stage-4 company's turns stay quick. The known misses close.

**Spec sections:** §17 (balance), §3 · **ADRs:** 0006, 0013, 0019 · **Formulas:** `docs/formulas.md` §30.6–§30.9, with §21, §26.4, §27, §28 · **Balance:** `docs/balance-targets.md` (known misses) · **Depends on:** M14 (`m14-done`) · **Lane:** A, alongside M15b

## Lane

- **Lane A,** its own session and branch (`m15a-balance`). **Merge order: M15a merges second.** Before merging: merge `main` (with M15b), re-parent any migrations, regenerate golden snapshots once with both milestones' reasons in CHANGELOG, and re-run every guard and every §30.7 target on the combined code.
- **M15a owns:** `backend/tst/balance/` (strategies, the new targets module), `tools/balance_runner.py` and new target tools, `known_misses.py`, `eras.yaml` (appending the §30.8 eras), `.github/workflows/` (the weekly long-run workflow), the 30-year perf test, and tuning any existing v2 key in `balance.yaml` (`rnd.*`, `pitch.*`, `mna.*`, `integration.*`, `debt.*`, `macro.*`, `finance.*`, `rivals.*`), each change recorded with its before and after.
- **M15a must not edit:** `score.py`, `modes/`, rankings, the continue-until loop, `scenarios.yaml` or M15b's screens.
- **Shared files:** `balance.yaml` (both lanes; keep both sides), `docs/formulas.md` (notes in §30.6–§30.9 only), `CHANGELOG.md`, `docs/data-dictionary.md`.
- **RNG:** none expected for strategies (they are scripts); future eras use `era_window` (31) by appended index; 44 is reserved if needed.

## Out of scope

New game systems. Scores and modes (M15b). The advisor and patents (backlog).

## Sub-tasks (commit after each)

1. **Strategies** (§30.6): steady_regions (from M13b), research_heavy, acquirer (from M14), integrator, ceo, in the balance scripts only. A smoke test plays each for 24 months on one seed.
2. **Eras to 2039** (§30.8): append the five eras; the seeded-window tests extend to them (inside the window on 30 seeds, earlier eras' months unchanged).
3. **Long runs:**
   - A 30-year runner mode (to Dec 2039) for steady_regions and research_heavy.
   - A **weekly** workflow (`.github/workflows/weekly.yml`, Sundays, and on demand) that runs the 30-year targets (V5, V6); the nightly keeps the 10-year targets.
   - The V6 perf test: build a 2039 stage-4 save from a 30-year run (a fixture tool), then time turns (median of three blocks after a warm-up).
4. **Measure, then tune** (§30.7): print every v1, v2 and §30.7 target for the nine strategies.
   - **V2 research:** tune `rnd.*` if research_heavy is above 1.4× or wins more than 4/10.
   - **V1 and T2:** with nine strategies, T2's wins should split; if steady still dominates, tune what it exploits (record the cause) rather than the measure.
   - **V7 covenants:** re-measure M10.T3 as breaches while cash is still positive; tune `debt.*` if needed.
   - **T5:** apply Reece's §30.9 decision.
   - Carried follow-ups to check and fix where a key can: late-round sizing (blitzscale's idle billions: investors size Series C/D to 24 months of burn), rivals' feature pushes in fast categories (AMD's bankruptcy around 2020), score-8 CPOs' hit rate, the M8 support and seat targets, launches per category at exactly 1.00.
5. **Known misses:** each one closed (removed from `known_misses.py`) or carried to v3 only with Reece's decision recorded.
6. **Close-out:**
   - `docs/balance-targets.md`: a "v2 final" section with every target's value.
   - A v2 balance summary for the retrospective (`docs/reviews/v2-balance.md`): what was tuned, what moved, what remains.
   - CHANGELOG; README index row.
   - Re-run M13b's §27.5 and M14's §28.9 targets on the final keys; every one in band.

## Acceptance criteria

- [ ] §30.7 V1–V7 met (printed, values recorded), on the combined code with M15b.
- [ ] Every earlier milestone's targets still pass on the final keys.
- [ ] `known_misses.py` is empty, or each remaining entry carries Reece's recorded decision.
- [ ] The weekly workflow runs green once (triggered by hand).
- [ ] `make check` green; `make e2e` passes; merged after M15b through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m15a-done`. That tag closes v2.

## Manual check (Reece, after merge)

Play one long game with Continue until from 2010 to 2039. Do the 2030s still feel like there's something to chase?

## Playtest 3 addendum

_(Product manager adds items from Reece's playtest 3 that touch this lane.)_

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
