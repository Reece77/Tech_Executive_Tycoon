# M10: Capital and macro (lane B)

**Goal:** the economy has a history and a future, and money has more shapes. Interest rates, the venture climate, consumer confidence and AI compute prices follow the real path from 2010 to 2025, then move in seeded cycles with occasional downturns. Companies can raise Series C and D from growth investors, or borrow, through venture debt and bank loans with covenants that bite when they're broken.

**Spec sections:** §9 (macro layer), §10 (instruments) · **ADRs:** 0002, 0003, 0005, 0013 (stream `macro` id 21, reserved), 0018, 0019 · **Formulas:** `docs/formulas.md` §20 (all), with §14 and §16 · **Wireframes:** `docs/wireframes.md` (M10 screens) and `docs/wireframes/source/Debt.dc.html` · **Roadmap:** `docs/v2-roadmap.md` (lane rules) · **Depends on:** M8r (`m8r-done`)

## Lane

- **Lane B.** It runs at the same time as M9 (lane A) in its own Claude Code session, git worktree and branch (for example `git worktree add ../tst-m10 -b m10-capital-macro main`).
- **Merge order: M10 merges first.** M9 then merges `main` into its branch, re-parents its migrations and regenerates golden snapshots.
- **M10 owns:**
  - `backend/tst/sim/finance/` (new `debt.py`, `macro.py` and the round-series changes) and `backend/tst/api/` finance routes;
  - `backend/data/investors.yaml`, `macro_history.yaml`, `climate.yaml` (folded into macro) and `accounts.yaml`;
  - `backend/data/events/lender.yaml`;
  - the Finance screen's tabs and the Market screen's macro strip.
- **M10 must not edit:** `cities.yaml`, `categories.yaml`, `incumbents.yaml`, the market phase's regional code, recruitment, or the Org screen. Those belong to M9.
- **Shared files:**
  - `balance.yaml`: add only `macro.*` and `debt.*` sections;
  - `docs/formulas.md`: notes in §20 only;
  - `CHANGELOG.md`, `docs/data-dictionary.md`: keep both sides.
- **Shared hook:** consumer confidence scales adoption in the market phase (§20.1). Put it behind one function, `macro.adoption_factor(state, segment_key)`, called once where adoption is used today. M9 will call the same function from its regional market code.
- **RNG:** stream `macro` (id 21), reserved in ADR-0013. Move its row into the main table.

## Out of scope

Cities, offices and regional markets (M9). IPO, public share price and Series E onward (M13). Debt for rivals (rivals keep §15's funding). Personal finance and stock trading (v3).

## Sub-tasks (commit after each)

1. **Data and formula tests:**
   - `macro_history.yaml`: monthly 2010–2025 for the base rate and consumer confidence; climate and the AI index by year, from the existing tables.
   - `macro.*` and `debt.*` keys, the growth investors, the lender templates.
   - Every §20.6 worked example as a unit test.
2. **Macro layer** (§20.1):
   - Indicators in phase 1 from history, then AR(1) on stream `macro`, with downturns.
   - The climate lookup replaced everywhere by `v`; the adoption factor; the AI index continued.
   - A migration storing each month's indicators (`macro_month`); update the data dictionary.
   - **Tests:** through 2025 the indicators equal history on every seed, and the venture climate equals `climate.yaml` (so v1 rounds are unchanged); a seeded test of the cycles after 2025; downturn spacing.
3. **Series C and D** (§20.2): the gates, heat, the board-seat rules and growth investors (SoftBank from 2017). Tests for gates and seats.
4. **Debt** (§20.3):
   - Venture debt and bank loans: gates, signing and warrants (cap table), monthly interest and principal, early repayment, statements.
   - Covenant checks; the `lender` event category with breach templates and their follow-up.
   - **Property tests:** the ledger balances with loans, and principal paid never exceeds principal borrowed.
5. **API, CLI and screens** (per the wireframes):
   - **Finance:** a **Debt** tab (loans, schedule, covenant headroom, Take a loan and Repay dialogs); Series C and D in Fundraising.
   - **Market:** a **Macro** strip (four indicators with sparklines, and "downturn under way").
   - **Supporting work:** glossary entries and driver breakdowns for the new numbers, History entries for loans, breaches and rounds.
   - **CLI:** `tst macro`, `tst loan --type --amount`, `tst repay`.
   - **Hidden values:** the hidden-value test covers that no future macro value is exposed.
6. **Balance, golden snapshots and e2e:**
   - The §20.5 targets, printed and recorded. Tune only `macro.*` and `debt.*`.
   - Golden snapshots regenerated only if consumer confidence moves them, with the reason in CHANGELOG.
   - **Playwright:**
     - (a) take venture debt after a round and see the schedule;
     - (b) a scripted covenant breach raises the lender event;
     - (c) the Market screen shows the macro strip with 2022's rate rise.
   - **Close-out:** CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every §20.6 worked example passes as a test.
- [ ] Through 2025, every indicator equals history on every seed, and the venture climate equals the old table.
- [ ] After 2025, cycles and downturns are seeded and reproducible; no API response contains a future value.
- [ ] Series C and D work with growth investors; the board-seat limits hold.
- [ ] Loans post interest and principal correctly (the ledger balances, property test); covenants raise the lender event and its follow-up.
- [ ] §20.5 targets met (printed, values recorded); all v1 and M8 targets still pass.
- [ ] `make check` green; `make e2e` passes; merged first in the pair, per CLAUDE.md §6, with the trailer `Milestone-Tag: m10-done`.

## Manual check (Reece, after merge)

On a stage-3 save, take venture debt after a round and watch the Debt tab for a year. Play into 2022 and see the rate rise on the macro strip.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
