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
4b. **Turn time at scale** (after M14's headcount work, 2026-11-06: 219 staff integrated 905 → 555 ms; timing tests now run serially in `check` via `make check-timing`). Carry it to a 2039 stage-4 company (V6): full garbage collections (250–580 ms at 220 staff, growing with object count) and reveal narrowing (about 6,900 rows rewritten a month at that size) are the next costs M14 measured. Fix with identical results (state-cache check, golden snapshots); keep the 1.0 s limit.
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

1. **Strategies** (§30.6) live in `backend/tst/balance/strategies_v2.py`, which imports only the game wrapper, the v1 scripts and the sim, so `tst.balance.report` can list all nine without an import cycle. `hire()` gained a `keep` set so a v2 script's own job posts (researchers, data-centre staff) stay open.
2. **The ceo strategy appoints its CEO at stage 4,** as soon as `ceo.min_stage` allows (§30.6 says stage 3; seats get authority from stage 3). Accepted by the product manager (2026-11-07).
3. **research_heavy** starts its research unit once the seed closes, on the domain with the largest summed `tech_weights` over its selling products, hiring the role whose skills that domain's research weighs most.
4. **integrator** builds general data centres in its home region, sized to the need a home data centre can serve (home and its neighbour), only when its cost per CU at full use is below spot; each is staffed by its own unit. Device plants follow only a hardware product, which the scripts never make. Placing builds in the region with the most uncovered need lowered the median margin from 43.7% to 34.2% and was reverted.
5. **New-category products** (product manager, 2026-11-07): steady_regions and every strategy built on it launch the CPO scoring's best new-category candidate (§27.1) at most once per 36 months, from the first launch and while steady would grow (profitable, or runway above 24 months).
6. **steady_regions splits steady's marketing:** 20% of last month's revenue as one budget over its products (each at least $10,000). steady sets the whole 20% on every product, which with four products spent about 80% of revenue; the v1 `steady` script is unchanged.
7. **Eras to 2039** (§30.8): appended as seeded windows. A two-domain era uses its first domain (humanoid robotics: AI; photonic interconnect: chip design). Effects the era model cannot express (the AR-glasses segment opening, the photonic data-centre cost cut) are left out (follow-ups).
8. **V5's total demand** is addressable customers × the category's reference price, home and other regions.
9. **V5's rival-launch clause** is checked over the categories rival startups may be founded in (§15.4); hardware and capacity categories are scheduled entrants only (§18.7, §26) and are printed (product manager, 2026-11-07).
10. **Rival launches after 2020** (ruling 3): `rivals.startup.start_feature_share` 0.3 (new key: a startup's product starts with that share of the features its market gained since January 2010; from 0, no late founder reached the 30% launch bar); a rival startup needs no manufacturing contract to launch (bug: rivals' manufacturing is abstract, §26.1); a rival startup down to one person closes (one-person startups held every `max_alive` place for decades). Regression tests: `tests/unit/test_m15a_rival_launches.py`.
11. **V3 re-banded** (product manager, 2026-11-07): the software integrator's margin gap at least −1 point (compute is about 12% of its revenue); a new `integrator_ai` arm against `ai_regions` (an AI-models first product) must show +3 to +10 points, a known miss owned by M23 (`V3.ai`).
12. **V4 re-banded to ≤ 1.4×** (product manager, 2026-11-07, second round): delegation with full authority stays within 40% of the hands-on script. `pitch.base` stays 0.15.
13. **V1 counts wins among the founder-played strategies;** the ceo arm is a delegation benchmark measured by V4 (product manager, 2026-11-07, second round).
14. **V7:** M10's §20.5 target 3 is measured as breaches in a month whose closing cash is still positive; `debt.venture.covenant_burn_months` 3 → 2 (60% on seeds 1–10 and 11–40, was 70%; blitz_debt bankruptcy 0%, was 20%); M10's §20.5 targets 2–5 pass. M10.T3 leaves the known misses.
15. **The weekly targets** (V1 over 30 seeds, V5, V6) run in `.github/workflows/weekly.yml` (Sundays and on demand); the nightly keeps the ten-year targets. Tests marked `weekly` are left out of `make check` and the nightly.
16. **The V6 save** is built by `tools/v6_save.py` playing research_heavy for 360 months through the normal save path. Writing only the final state to a save failed the state-cache check: the next turn rebuilt the macro history it did not have.
17. **Small rival startups close** (product manager, 2026-11-07, third round): below `rivals.startup.small_staff` (3) people for `rivals.startup.small_months` (24) consecutive month ends, a rival startup closes, shut down or acqui-hired, with its own History line; persisted in `startup_small` (migration `0036_m15a`). It replaces ruling 3's one-person close. Tests: `tests/unit/test_m15a_rival_launches.py`.
18. **V5's launch clause re-banded** (third round): at least 90% of (run, startup category, decade after 2020) cells have a rival launch, and no category misses a decade in more than 2 of 10 runs; the old clause failed on one empty cell of 160.
19. **`rnd.rate` 0.4 → 0.3** for V2: research_heavy won 5 of 10 among the founder-played strategies; M11's §21.8 targets 2, 3 and 5 still pass (target 2: 1.14 net).
20. **Game records** each month's revenue and operating result (`Game.pnl`) for V3's margin, the last 12 months.

## Follow-ups

- v3 (devices): the AR-glasses era's new consumer device segment (§30.8).
- v3 (fabs): the photonic-interconnect era's data-centre cost per CU −15% (§30.8).
- v3: seeded future entrants for hardware and cloud after 2025 (V5's scheduled-only categories).
- M23: `integrator_ai` (V3.ai): an AI-models company's own GPU data centres add under 1 point of margin at year 10.
