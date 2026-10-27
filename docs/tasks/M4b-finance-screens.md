# M4b: Finance screens

**Goal:** run the company's money from the browser: read the statements, see the cap table, raise SAFEs and priced rounds with a clear view of dilution, watch the board, and see how a game ends.

**Spec sections:** §10, §13 · **ADRs:** 0007, 0009, 0014, 0018 · **Wireframes:** `docs/wireframes.md` (M4b screens) and `docs/wireframes/source/Finance.dc.html`, `CapTable.dc.html`, `Fundraising.dc.html`, `Board.dc.html`, `GameOver.dc.html` · **Depends on:** M4a (`m4a-done`)

## Context

M4a provides every rule, endpoint and preview. This milestone is front end only: display, sort, filter and format what the API returns; never compute a game value (`CLAUDE.md` §7). If a screen needs a value the API lacks, add it to the backend schema, regenerate the client, and record it under Decisions made.

## Out of scope

Any new rule beyond the backend slice. Competitors and History screens.

## Backend slice (sub-task 0)

1. **Bridge amount at acceptance** (`docs/formulas.md` §14.7): `3 × projected net burn + max(0, −cash)`, computed when the bridge is accepted; the offer and the API show today's amount. Test: a bridge accepted in the third month of insolvency leaves cash positive.
2. **Option pool in the screens:** the offer dialog and hiring meta use `option_pool_left_bp`; retire `hiring.option_pool_bp` from `balance.yaml`, `formulas.md` §12 and the API (M4a follow-up).
3. **Stage history:** store the turn each stage is reached (M3b and M4a follow-up) and expose it, so tiles can say "Stage 2 since Jan 2012".

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

0. Backend slice (above).
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

- **Bridge sizing (sub-task 0).** `bridge_amount` = `round(bankruptcy.bridge_burn_months × max(projected net burn, 0)) + max(0, −cash)`, computed by the accept action from the ledger at that moment and stored on the bridge; the offer stores the same formula's value at the offer, and `GET /finance/safes` and `/finance/summary` show today's value for an open offer. The bridge-offered inbox text says the amount is set on acceptance. `insolvency()` no longer needs the opening balances.
- **Option pool (sub-task 0).** `hiring.option_pool_bp` is gone from `balance.yaml`, `HiringBalance`, the hiring meta and formulas.md §12; the M1b worked-example test now checks only `max_offer_equity_bp` (the key it also checked no longer exists). The offer preview adds `options`, `fraction`, `options_left` and `fd_shares`; the offer dialog shows options and their share of FD, and the hiring-plan dialog says "bp left in the option pool".
- **Stage history (sub-task 0).** `CompanyState.stage_history` holds `(stage, turn)` pairs, written only through `reach_stage()` (first hire, ARR, funding). New games start with `(0, 0)`; incumbents and saves upgraded by migration 0010 start empty, so their "since" is null rather than a guess. The Overview's ARR tile says "Stage N since <month>" (the M3b tile's missing date).
- **Director history in its own table.** `board_seat_history` (one row per seat, a JSON list) instead of a column on `board_seat`: migration 0009 inserts `board_seat` rows built from the current ORM model, so a new column there breaks upgrades from pre-0009 saves. `board.history_months` (6) and `board.trend_points` (2) are new balance keys.
- **Values the screens needed, added to the API** (CLAUDE.md §7): statement totals (`total_cost_of_revenue_cents`, `total_operating_expenses_cents`, `total_liabilities_cents`) and `burn_cents`; on the cap table `is_founder` per holder, founder shares and fraction, last round label, date and post-money, `ownership_history` (FD after a round is `fd_pre + new_shares`; a SAFE shows the fraction unchanged until it converts), vesting rule, and `next_vest_*` per grant (`next_vesting`, `at_cliff` in `sim/finance/options.py`); `founder_fraction_after` per open term sheet (the closing function, as the preview uses); `firms_asked` per round; the next series' `gate_arr_cents` and energy; the preview's `holder_kind`, `is_founder`, `new` per line, `founder_keeps_tie`, energy and series label; the SAFE list's `blocked` reason and energy; the board's seats by kind, `removal_possible`, trend (rising, steady or slipping by `board.trend_points` over the shared history), expected and actual growth (`actual_growth`), next meeting (`next_meeting_turn`) and the last meeting from the inbox; the finance summary's open bridge (id, today's amount, deadline) and bridge energy; the Overview's `funding` tile and stage history; `options` on a profile's employment; and `GET /finance/game-over`.
- **Game over (ADR-0018).** When Continue ends the game the app opens `/game/:id/over` (no nav). The screen's timeline is the last six months of Finance inbox items. An unanswered bridge at bankruptcy counts as lapsed (`bridge_lapsed`): it was offered for the turn that ended the game, so its status is still `offered`. Other screens stay readable with a "game is over" banner and Continue disabled; the top bar shows a Game over badge linking back to the summary.
- **Runway "Profitable".** `formatRunway(null)` reads "Profitable" (formulas.md 14.1); the M1 test expecting "Not burning" now expects the M4 wording.
- **Insolvent badge.** Shown while the top bar's cash is negative (a sign check on an API value, not a computed game value); it links to Fundraising, where an open bridge is the first panel, and says "bridge offered" when there is one.
- **Statements.** The last 12 periods side by side (the brief; the wireframe drew six). The balance sheet and cash flow are the latest period's. A period still in progress is marked with an asterisk. The cash and burn chart uses the Overview's 12 snapshots on two axes.
- **Finance routes.** `/finance/:tab` with tabs `statements`, `captable`, `fundraising`, `board`; key 7 opens Statements. Inbox Finance messages get a gold "Finance" badge, a Finance filter, and a button to the tab that fits the message.
- **E2E (sub-task 5).** (a) and (b) share a garage save at seed 16 (the seed the backend fundraising tests use, where several firms answer). (c) scripts a funded spinout through the API that hires four engineers at 40× their ask so cash runs out in April 2010 while the board is still above 40 and offers a bridge; the test then ignores it through the UI. Locally the run used `PLAYWRIGHT_CHANNEL=msedge`, as in M3b.
- **M3b e2e setup funded.** Since M4a's bankruptcy rule, the M3b flow's company (four people, no revenue) went bankrupt in December 2010 before Pipeline could launch, and the app now opens the game over screen. Its API setup raises a $1M SAFE at a $2.5M cap (again if declined) so the product flow keeps its runway; the assertions are unchanged. The smoke test's key 7 now opens Finance and key 8 says M5.

## Follow-ups

- **Balance (Reece's manual check).** In the scripted bust the bridge offer was $2.9M against a $1.1M deficit: three months of a very high burn. Worth checking that bridges feel right at normal burn rates.
- **Tie wording after Series B.** `founder_keeps_tie` is false once investor and independent seats are a majority; the preview then says "investors can outvote you". A per-director "would vote now" view could make removal risk easier to read.
- **History screen (M7).** The ownership-over-time and stage history now exist in the API and could feed it.
- **Playwright Chromium.** This machine runs e2e with `PLAYWRIGHT_CHANNEL=msedge`; `pnpm exec playwright install chromium` would let `make e2e` run as written.
