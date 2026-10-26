# M4a: Finance (rules, API, CLI)

**Goal:** the company has statements that reconcile every month, a cap table in shares with vesting options, SAFEs and priced Seed, Series A and Series B rounds from investor firms, a board whose confidence can remove the founder, and bankruptcy, all through the API and the command line, fully tested. Screens come in M4b.

**Spec sections:** §3, §5.4, §10 · **ADRs:** 0002, 0003, 0004, 0006, 0011, 0013, 0014, 0018 · **Formulas:** `docs/formulas.md` §14 (all), plus the M4 rows in §6, §7, §8, §10 and §12 · **Depends on:** M3 (`m3b-done`)

## Context

M3 gave the company revenue. Cash can still fall forever without consequence, equity is a flat percentage, and nobody but the player has a say. M4 adds the startup's money side: the founder can raise on a SAFE early, run priced rounds once there is traction, pay for that money in dilution and board seats, and lose the company by running out of cash or the board's patience. This is the first milestone where a game can end (ADR-0018).

`docs/formulas.md` §14 is authoritative for every rule and number. Investor firms, scenario cap tables and the funding climate are data (`investors.yaml`, `scenarios.yaml`, `climate.yaml`); tunables are in `balance.yaml` (§12).

## Out of scope

Venture debt and bank loans, interest and covenants, Series C onward, convertible notes and SAFE discounts, liquidation waterfalls and exits, IPO and public stock, M&A (all v2). The Sandbox mode (M7). Board events and director storylines (M6). Finance screens and the game-over screen (M4b).

## Rules (summary of `docs/formulas.md` §14)

1. **Statements** are views over the ledger: P&L, balance sheet (with an accumulated result) and cash flow, which reconcile every turn.
2. **Cap table in shares:** 10,000,000 at start, held per scenario; offers in bp become option grants from the unallocated pool; 4-year vesting with a 1-year cliff; unvested options improve retention once there is a share price.
3. **Investors value the company** from ARR, 6-month growth and the funding climate, with a floor for young companies.
4. **SAFEs** (post-money cap) are answered once, all or nothing, the next turn.
5. **Priced rounds:** start a round, firms send term sheets the next turn, accept one, it closes at Continue with a pool top-up, SAFE conversion, new preferred shares, fees and a board seat.
6. **Board:** seats grow with each round; confidence follows growth against expectation and runway; a majority of directors below 25 for 3 months removes the founder.
7. **Bankruptcy:** 3 consecutive month-ends with negative cash; a bridge SAFE from existing investors may be offered once per insolvency.
8. **Stages** 2 and 3 also come from a closed seed and a closed Series B.

## Sub-tasks (commit after each)

1. **Data and formula tests:** `investors.yaml`, `climate.yaml`, cap tables in `scenarios.yaml`, all §12 M4 keys in `balance.yaml`. Every §14.10 worked example as a unit test (noise off), including the full dilution table.
2. **State and persistence:** `cap_table_entry` (holder: person, firm or group; class; shares), `option_grant` (employment, granted, start turn, vested, forfeited), `safe` (amount, cap, status, turn, converted round), `funding_round` (series, status, target, opened turn, closing data), `term_sheet` (round, firm, pre-money, amount, status, expiry), `board_seat` (kind, holder person, firm, confidence, months below threshold), `save_meta.game_state` and `ended_turn`, `next_ids`. Migration `0009_finance`: existing saves get their scenario's cap table, and each employee's `equity_bp` becomes options at 1,000 per bp with a grant date of their hire turn. Data dictionary.
3. **Statements and runway** (§14.1) as pure functions over ledger lines, with the reconciliation invariant as a property test over random ledgers and over the golden run; projected runway shows "profitable" when the projection is positive.
4. **Cap table and options** (§14.2): grants on hire from the unallocated pool (replacing the M1 bp sum), vesting each month, forfeiture on leaving, the retention factor in §10. Property tests: holdings always sum to FD; vested never exceeds granted; the unallocated pool never goes negative.
5. **Fundraising** (§14.3–§14.5): `V_base`, SAFEs (action and phase 7 answer), rounds (start, term sheets in phase 7, accept, close in phase 1 with the §14.5 closing function), down rounds, fees and ledger entries, stream `finance` (id 16). Property test for the closing function per ADR-0018 §3.
6. **Board** (§14.6): seats per round, generated directors, monthly confidence in phase 10, quarterly meeting summaries, warnings, removal votes.
7. **Insolvency and game over** (§14.7, ADR-0018): insolvency notes, the bridge offer and its acceptance, bankruptcy after 3 months, `game_state`, refusal of `advance_turn` and actions once ended. Stage gates from funding (§14.8).
8. **API** (save-scoped): statements (P&L, balance sheet, cash flow by month, quarter or year), cap table (holders, classes, shares, percentages; per-employee grants with vested and unvested), rounds and term sheets, SAFEs, board (seats, directors, average and per-director confidence, months below threshold), the SAFE hint band (§14.9), a round preview that shows the dilution of accepting a given term sheet (each holder's percentage before and after, the pool top-up, SAFE conversion), runway, and `game_state`. Extend the hidden-field test: no response contains `V_base`, `bias`, acceptance probabilities or noise.
9. **CLI:** `tst statements --period month|quarter|year`, `tst captable`, `tst safe --amount --cap`, `tst round start --series --target`, `tst round sheets`, `tst round accept --sheet`, `tst bridge accept`, `tst board`.
10. **Golden and balance checks:**
    - Golden script: a SAFE around turn 3 at a cap near `1.2 V_base`, a seed round once the product is live, a Series A once ARR passes $1M; regenerate snapshots with a CHANGELOG note (cash, ownership and board confidence join the snapshot).
    - **Three-round dilution** (the spec's M4 criterion): a scripted SAFE, seed, Series A and Series B reproduce the §14.10 table to the share.
    - **Funding diagnostics** (printed, no thresholds): on 10 seeds, (a) the M3a earn-and-burn script in `funded_spinout` with no fundraising (M3a measured it cash-positive at turn 36, so it should survive); (b) the same script hiring to 15 staff by turn 12, with no fundraising (report the bankruptcy turn, if any); (c) as (b), raising a Series A at the best term sheet as soon as ARR allows (report the turn, pre-money, amount, founder ownership after, and survival to turn 60). Record the table under Decisions made; do not tune to it.

## Acceptance criteria

- [ ] Every §14.10 worked example passes as a test, including the dilution table to the share.
- [ ] P&L, balance sheet and cash flow reconcile on every turn of the golden run and under property tests.
- [ ] A SAFE, a seed, a Series A and a Series B can be raised through the API and the CLI; the round preview matches the cap table after closing.
- [ ] Offers grant options from the pool; vesting, forfeiture and the retention factor work; old saves convert bp to options.
- [ ] The board forms, its confidence follows §14.6, quarterly summaries and warnings appear, and a scripted collapse after Series B removes the founder (game over), while the same collapse after Series A does not.
- [ ] Three months of negative cash ends the game; a bridge accepted in time prevents it; after game over, advancing and actions are refused with 409 and reads still work.
- [ ] Funding diagnostics printed and recorded under Decisions made.
- [ ] Replay reproduces a save with a SAFE, two rounds and a bridge.
- [ ] No API response leaks a hidden field or a §14.9 forbidden value (exact-name test).
- [ ] 120 turns with 25 staff, 3 products, a board and all incumbents average under 1 second per turn (printed).
- [ ] `make check` green; golden snapshots regenerated with a CHANGELOG note.

## Manual check (Reece, command line, optional)

1. Start a `garage_bootstrap` game; `tst safe --amount 300000 --cap 4000000`; advance and read the inbox.
2. Build and launch a product; when it is live, `tst round start --series seed --target 1500000`; advance; `tst round sheets`; accept one; advance; `tst captable` and `tst board`.
3. Let cash run out and watch the insolvency notes, the bridge offer and, if you ignore it, the end of the game.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
