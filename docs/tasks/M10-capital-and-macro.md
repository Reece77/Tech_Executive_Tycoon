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

Engineering details are in `docs/formulas.md` §20.7. The ones that touch design or the lane rules:

1. **Series C and D keys sit in v1's maps** (`finance.round.gate_arr_cents`, `typical_cents`, `board.expected_growth`, `board.seats`, plus `board.max_seats`), not in `macro.*`/`debt.*`: the code reads every series from those maps, and the keys are new (no v1 value changed); M9 does not touch these sections. Expected growth after a C is 0.8 a year, after a D 0.6 (not in the spec; a growth-stage board expects less than a Series B board).
2. **The adoption hook takes `balance`:** `macro.adoption_factor(state, segment_key, balance)`, because the segments and exponent are balance data. M9's regional code calls it with the same three arguments.
3. **Which month is current:** history while the calendar is inside it (public), else the last month phase 1 set; so v1's climate is exactly unchanged through 2025 and nothing after 2025 is ever shown or used ahead of time.
4. **Downturn spacing:** 36 months from the end of the previous downturn.
5. **Lender events** are queued by the engine (trigger `covenant_breach`, never drawn by the director) and always written from their template, since their choices are the §20.3 terms. Their effects are new effect types (`loan_fee`, `loan_rate`, `loan_repay`) whose size is a share of `debt.breach`; the waiver fee is also held to the critical cash cap (§16.3). The waiver fee posts to `7000_interest`.
6. **Cure period:** after a breach, covenants rest for 3 months (`debt.breach.cure_months`) so the player's answer can work; a breach found after that and within 6 months of the first calls the loan. Without it a breach that persisted into next month would call the loan before the answer could matter.
7. **Covenants read completed months** (last month's burn; the last 3 months' operating result, kept in `finance_history`) and this month's cash after the loan payments. The bank loan's gate wants an operating profit in each of the last 3 months; its covenant wants their sum above zero.
8. **Principal after a partial repayment** is re-spread over the months left (the term never extends); without one it is exactly equal principal.
9. **Warrants** make the lender hold exactly 0.25% of FD after issue. Lenders: Silicon Valley Bank (venture debt to 2022), Hercules Capital (from 2023), JPMorgan Chase (bank loans), in `investors.yaml`.
10. **Golden snapshots** were regenerated here, as the brief allows when consumer confidence moves them (reason in CHANGELOG).

**Results** (docs/balance-targets.md, M10): every v1 target as before (T2 the recorded M7c miss; blitzscale T3 now 4/10), S2 12.4 worker-minutes run alone (22.6 under the parallel suite). §20.5: target 2 +5.2 founder points and +0 bankruptcy (pass); target 4 41/50 and sd 0.171 (pass); target 5 8/10 (pass). Recorded misses, `xfail(strict=False)` for M15 (Reece, 2026-11-01): §20.5 target 3 at 90% (blitzscale with debt is below zero cash before its next round on 8/10 seeds, so no `debt.*` value brings it to 20-60%), and M8 target 3 at 1.069 (1.088 before; confidence lifts SMB adoption in both arms).

## Follow-ups

- M15: §20.5 target 3 needs a different measure or script (for example breaches while cash is still positive, or debt only after Series A and B).
- M15: M8 target 3 (support) at 1.069.
- Rivals do not borrow (out of scope); M13 can price public markets off the base rate.
- The macro strip shows two years; a longer History chart of the indicators would be cheap (`macro_month` holds every month).
