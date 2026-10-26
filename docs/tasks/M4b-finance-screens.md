# M4b: Finance screens

**Goal:** run the company's money from the browser: read the statements, see the cap table, raise SAFEs and priced rounds with a clear view of dilution, watch the board, and see how a game ends.

**Spec sections:** §10, §13 · **ADRs:** 0007, 0009, 0014, 0018 · **Wireframes:** `docs/wireframes.md` (M4b screens) and `docs/wireframes/source/Finance.dc.html`, `CapTable.dc.html`, `Fundraising.dc.html`, `Board.dc.html`, `GameOver.dc.html` · **Depends on:** M4a (`m4a-done`)

## Context

M4a provides every rule, endpoint and preview. This milestone is front end only: display, sort, filter and format what the API returns; never compute a game value (`CLAUDE.md` §7). If a screen needs a value the API lacks, add it to the backend schema, regenerate the client, and record it under Decisions made.

## Out of scope

Any new rule. Competitors and History screens.

## Screens

1. **Finance** (nav key 7, now live), with tabs:
   - *Statements:* P&L, balance sheet and cash flow, by month, quarter or year, with the last 12 periods side by side and a cash and burn chart.
   - *Cap table:* holders by class with shares and percentages, the option pool (granted, vested, unallocated), and a dilution history across rounds.
   - *Fundraising:* raise on a SAFE (amount, cap, the hint band); start a round (series, target, guidance range); open term sheets side by side (firm, pre-money, amount, board seat, expiry) with the dilution preview for each; past rounds and SAFEs.
   - *Board:* seats and directors, each director's confidence with its trend, months below the removal threshold, and the last quarterly summary.
2. **Game over screen:** reason (bankruptcy or removal), the turn, final cash, ARR, headcount and ownership, and links to read the save (statements, cap table, inbox).
3. **Top bar:** runway shows "Profitable" when it applies; an Insolvent badge while cash is negative, linking to the bridge offer if one is open.
4. **Offer dialog and profile:** equity shown as options and percentage; the profile's contract panel shows granted, vested and unvested options and the vesting date of the next tranche.
5. **Overview:** a funding tile (last round, post-money, founder ownership, board confidence label).
6. **Inbox:** a Finance kind for SAFE answers, term sheets, closings, board summaries, warnings, insolvency and bridges.

## Sub-tasks (commit after each)

1. Regenerate the client; shared `StatementTable`, `CapTable` and `DilutionPreview` components with tests.
2. Finance screen: Statements and Cap table tabs.
3. Finance screen: Fundraising and Board tabs.
4. Game over screen, top bar, offer dialog, profile, Overview and Inbox additions.
5. Playwright: (a) raise a SAFE and see the answer at Continue; (b) start a seed, compare two term sheets' dilution previews, accept one, Continue, and see the cap table match the preview; (c) run out of cash in a scripted save, see the insolvency badge and bridge, ignore it, and reach the game over screen.

## Acceptance criteria

- [ ] Every M4a finance action is reachable from the screens, with its preview or hint shown first.
- [ ] Screens match their wireframes and stay usable with 3 rounds, 2 SAFEs, 40 option holders and a 6-seat board.
- [ ] No game value is computed in the front end.
- [ ] `make check` green; `make e2e` passes all flows.

## Manual check (Reece)

Play a `garage_bootstrap` game to a Series A. Note whether raising feels like a real decision (cap versus chance, valuation versus dilution, board seats), and whether the board's mood is readable before it turns against you. These notes feed the balance pass and M5.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
