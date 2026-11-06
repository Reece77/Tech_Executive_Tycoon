# M15b: Game modes and polish (lane B)

**Goal:** v2 becomes a game you can play in more than one way. A company score rates any company. Sandbox lets you start in any year with your own settings and play forever. Five historical scenarios give short, goal-driven runs. Yearly industry rankings give you lists to climb. "Continue until something needs me" makes the long late game quick to play. And every v2 number and event has its glossary entry and History line.

**Spec sections:** §3 (scenarios, Sandbox, company score), §17 · **ADRs:** 0002, 0006 (campaign length), 0011, 0019 · **Formulas:** `docs/formulas.md` §30.1–§30.5 · **Backlog:** `docs/ideas-backlog.md` (historical scenarios, industry rankings, skip to the next decision) · **Depends on:** M14 (`m14-done`) · **Lane:** B, alongside M15a

## Lane

- **Lane B,** its own session and branch (`m15b-modes`). **Merge order: M15b merges first;** M15a then merges `main`, regenerates golden snapshots and measures balance on the combined code.
- **M15b owns:** new `backend/tst/sim/score.py`, `backend/tst/sim/modes/` (Sandbox and scenarios), the rankings code, the continue-until loop (API and CLI), `backend/data/scenarios.yaml`, the New game, Scenario and Rankings screens, the result screen, the glossary and History audit, and the preferred-share conversion at the IPO.
- **M15b must not edit:** `backend/tst/balance/`, `tools/balance_runner.py`, the strategies, `known_misses.py`, `eras.yaml`, `.github/workflows/` (M15a's).
- **Shared files:** `balance.yaml` (add only `score.*`, `rank.*`, `sandbox.*`), `docs/formulas.md` (notes in §30.1–§30.5 only), `CHANGELOG.md`, `docs/data-dictionary.md`: keep both sides.
- **RNG:** none expected; if one is needed, use 43 (44 is lane A's).

## Out of scope

The chief-of-staff advisor, patents, achievements (backlog). The mineral-first start (v3). New balance strategies (M15a).

## Sub-tasks (commit after each)

1. **Company score** (§30.1): the pure function, December and game-end snapshots, the API field for every company (public inputs only), the §30.1 example as a unit test. Shown on the Overview and Rival screens.
2. **World building at any start year:** generalise the fixture tools' start-at-year path into one engine function used by Sandbox and scenarios (history applied to that date: macro, supply, eras, incumbents' listings, rivals' state). **Test:** a 2015 start's macro, components and eras equal a 2010 game's values in 2015 on the same seed.
3. **Sandbox** (§30.2): the options, no campaign end, no board removal, the Sandbox flag on the save, kept out of the Hall of Fame.
4. **Scenarios** (§30.3): `scenarios.yaml`, the five starts and goals, goal checks, the result screen. **Tests:** each scenario loads, and its goal check passes on a scripted success and fails on a scripted failure.
5. **Rankings** (§30.4): the three lists each January, the news items, the Rankings screen, the hiring and brand effects.
6. **Continue until** (§30.5): the loop and its stop conditions; a button beside Continue and `tst advance --until-needed`. **Test:** each stop condition stops it; it never decides anything.
7. **Polish:**
   - **Glossary and History audit:** every number shown on a v2 screen (M8–M14b) has a glossary entry, and every v2 event type writes a History line; add a test that scans the API schemas' numeric fields against the glossary keys.
   - **Preferred shares convert to common at the IPO** (an M13 follow-up), with a migration if the cap table needs one.
   - The M13b follow-ups that are pure UI: Modify prefills every pitch kind's dialog; reports show quarter-start values ("41 → 47").
8. **API, CLI, e2e and close-out:**
   - **CLI:** `tst new-game --sandbox --year`, `tst new-game --scenario`, `tst rankings`, `tst score`.
   - **Playwright:** (a) start a Sandbox game in 2018 with no rivals and see the 2018 world; (b) start "Survive 2022", play to the deadline on a fixture that succeeds, and see the result screen; (c) the January rankings arrive as news and on the Rankings screen; (d) Continue until stops at a pitch.
   - Golden snapshots: unchanged for a standard game except the score snapshot fields (regenerate once if needed, reason in CHANGELOG).
   - No new xfails; report and stop on any guard that fails against `main` and that M15b's keys can't fix.
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] The §30.1 example passes as a test; the score uses public inputs only.
- [ ] A Sandbox or scenario start in year Y has the same world as a 2010 game in year Y on the same seed.
- [ ] All five scenarios load and judge their goals.
- [ ] The glossary covers every numeric API field on v2 screens (test).
- [ ] `make check` green; `make e2e` passes; merged first in the pair through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m15b-done`.

## Manual check (Reece, after merge)

Start the AI lab scenario and try to cause Transformers first. Then start a Sandbox game in 2020 and use Continue until for a year.

## Playtest 3 addendum

_(Product manager adds items from Reece's playtest 3 that touch this lane.)_

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
