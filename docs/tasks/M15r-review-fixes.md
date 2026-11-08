# M15r: Fixes from Codex review 4

**Goal:** fix the findings of the fourth outside review (`docs/reviews/codex-review-4.md`, Codex, at `m15b-done`) before v3 builds on the M&A, exit and pitch code.

**ADRs:** 0002, 0003, 0004, 0005, 0013, 0015, 0020 · **Formulas:** §26.8, §27.1, §28.2–§28.5, §28.11, M15b addendum 10 · **Depends on:** M15a (`m15a-done`) · **Lane:** alongside M16 (lane A) and M24 (lane C)

## Context

The product manager triaged the review on 2026-11-07 and confirmed the findings against the source (no P1). **Findings 2 and 3** (consolidation membership by period, and nested groups split by `owner_of` and `group_companies`) go to **M16**, which rebuilds the group model; M15r must not edit consolidation or the group helpers. The other nine are fixed here, each with the regression test the finding asks for, written first and seen failing.

## Lane

- Its own session and branch (`m15r-fixes`). **Merge order:** M24 first, then M15r, then M16 (M16 regenerates goldens on the combined code).
- **M15r owns** the files the nine findings name: `mna/exit.py`, `modes/serial.py`, `db/state_io.py`'s public-company sync, `org/pitches.py`'s acquisition and plant candidates, `mna/integration.py`'s post-close problems, `mna/deals.py` and `mna/closing.py` money splits, migration fixes for `production_contract.price_cents`, `docs/data-dictionary.md` blocks for 0030–0035, `tests/unit/test_mna_pitches.py`.
- **M15r must not edit:** `finance/consolidation.py`, `state.group_companies`, `mna/antitrust.owner_of` (M16's findings 2 and 3), `backend/tst/sim/founder/` (M24).

## Sub-tasks (commit after each; regression test first)

1. **A sale settles the buyer's side** (finding 1). `sell_company` and `found_again` settle the sale once through the brand-closing path: the buyer's cash consideration, investment and goodwill postings, and an `Acquisition` record. A buyer that can't pay is refused, never silently skipped. **Test:** sell, found again, advance, cold reload: the buyer, brand and new venture ledgers reconcile, and nothing settles twice.
2. **Delisting persists** (finding 4). Remove the sold company's current `public_company` row in the same transaction (share-price history stays); end any IPO or CEO state the sale ends. **Test:** cold load after `FoundAgain` with `TST_STATE_CACHE_CHECK=1`.
3. **A stable identity for every venture** (finding 9). Each player venture gets a persisted stable key (a player namespace plus venture ordinal), used by every player-company stream (IPO demand, sentiment, the rest). **Test:** appending an unrelated incumbent leaves a new venture's draws unchanged.
4. **Acquisition pitches use public numbers only** (finding 5). The synergy term uses a public cost estimate (revealed staffing at market rates, publicly rounded) for ranking, wording and cases alike. **Test:** two targets differing only in a private salary give identical candidates, pitches and report facts.
5. **Plant pitches propose valid sizes** (finding 6). `_plants` chooses from the kind's sizes (`kind.sizes or balance.facility.sizes`) and the case uses the assembly variable costs and yield (§26.2). **Test:** a COO plant pitch approved creates the plant.
6. **Hidden problems apply to brands too** (finding 7). `tech_debt` and `customer_concentration` apply after closing in either mode, on the products' owning company. **Test:** both problems in both modes over all 12 months and their expiry.
7. **Exact money in deals** (finding 8). Cash and stock split through `money.exact` (or integer basis points), rounded once, shared by validation, closing and issuance; audit the other M&A price and fee helpers. `production_contract.price_cents` (migration 0031, FLOAT) moves to an exact representation (integer millicents or a numerator and denominator) in a new migration. **Tests:** rational-reference half-cent cases, including 0.545 at small and large prices.
8. **Data dictionary** (finding 10). One table per heading for `ceo`, `production_contract` and `production_month`; `departure.name`; the `refused` status; checked against migrations 0030–0035 and the ORM by script.
9. **Pitch tests that test something** (finding 11). The CPO test seeds an eligible startup, an incumbent and an over-limit startup and asserts the exact permitted targets; the Holiday test executes an acquisition pitch below the auto-approve limit and asserts it stays pending with no deal or posting.
10. **Close-out:** a Resolution section in `docs/reviews/codex-review-4.md` (findings 2 and 3 point to M16), CHANGELOG, golden snapshots only if a fix moves them (reason in CHANGELOG), the nightly guards once.

## Acceptance criteria

- [ ] Each of the nine findings has a regression test that failed before its fix and passes after.
- [ ] A sell-and-found-again cycle reconciles every ledger after a cold reload.
- [ ] No money path in M&A uses binary floats (tests against rational references).
- [ ] No guard that passed at `m15a-done` fails.
- [ ] `make check` green; `make e2e` passes; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m15r-done`.

## Decisions made

- **The sale settles at acceptance** (finding 1). Accepting the takeover bid runs the brand-closing postings (`closing.settle`, shared with `close_deal`): the buyer pays the price in cash and holds the brand's book equity in 1810 plus goodwill; the deal's mode is `brand` and the acquisition record carries no hidden problems (the buyer did no diligence; the player's company has none modelled). The seller's books do not change (a share sale). A buyer whose cash is short of the price is refused: no sale, a `deal_update` "The sale fell through", and the game goes on. The company becomes the buyer's brand (`parent_id`) when the founder founds again, as M15b built it; on Retire the game is over. The event choice path now passes the ledger balances (`apply_choice(..., balances=)`, `apply_public_step` returns entries).
- **Delisting** (finding 4): `state_io` deletes `public_company` rows and `board_seat` rows (with their history) that the new state dropped; the share-price history stays. A CEO serving the sold company ends with `end_reason` `acquired`. Listings stay as the IPO's history.
- **Venture key** (finding 9): `(VENTURE_KEY = 4, n)` for the player's n-th venture after the first, stored in `company_rival_key` (so it survives the sale too). `player_key()` keys the ipo, market_sentiment, mna and press streams; the first company keeps `(1,)`, so existing saves and goldens draw as before.
- **Public cost estimate** (finding 5): `deals.public_costs_cents` = displayed (15.5-rounded) headcount x a market head's monthly cost (the mean over the pool functions' roles of mid-level pay at the default region, benefits and office). Product costs (hosting, marketing) are not in it.
- **Plant case** (finding 6): 26.2's cost per good unit at the formula's base yield (0.85), as a plant has before staff.
- **Problems after closing** (finding 7): customer_concentration's churn runs months T+1 to T+12 after a closing at T (the integrate path had installed it at T, so it covered only 11 product months); it applies to rival acquirers too, as the mode-independent path. Integration's own churn penalty is unchanged.
- **Exact money** (finding 8): `deals.cash_part_cents` (Fraction, half-even once); the other M&A helpers multiply in Fractions (`money.exact`). Contract prices are integer millicents (`price_millicents`, migration `0038_m15r`; quantized at signing); the sim reads `price_cents` as a property.
- **Migration number**: written as `0036_m15r` on `0035_m15b`; renumbered `0037_m15r` on M15a's `0036_m15a`, then `0038_m15r` on M24's `0037_founder` at the merges.
- **e2e failures on `main` since M15a (second addendum, 2026-11-08)**: one root cause, the e2e helper, not a game rule. `continueMonth` read the top-bar date and waited for it to change. After `answerBlocking` answers an event it reloads the page, and the date reads "…" until the overview loads, so the wait passed on the page load alone and a Continue was counted that had not run (instrumented: "click continue at …", then "now Feb 2010" with the month never played). It bit whenever an event was answered first, so it surfaced as M15a's busier worlds (more rival launches, more press jabs and dependency events in the first months) raised such months; tracing hid it by slowing the browser (m9 failed 5/5 with `--trace off`, passed 8/8 with tracing). `pressContinue` now waits for the advance response and for the top bar to show the month it names; `continueMonth` = answer blocking events + `pressContinue`.
  - **m9 (b)** — fixture timing, not a rule: with real months the Europe launch goes live after its six localization months (passes 3/3 with `--trace off`; it never stayed "Localizing" once six months were played), so no engine change and no unit test.
  - **m14b (a), (b), (d)** — the same wait: (a) checked "kept" after a Continue that had not run, and (d) hung the same way through `continueMonth`; (b) had its own inline copy of the date wait, now `continueMonth`. 4/4, three runs.
  - **m13 (a)** — after each Continue the loop reloads and reads the IPO status; with the date wait that read could overlap a month still being played and see last month's status, leaving pricing or the next Continue to race. It now reads only after the advance response. It did not fail here in 10 runs on the old helper (including under CPU load), so the 2-in-4 failure on `main` is not reproduced locally; the time-based wait it depended on is gone.
  - m10c (b) used the same inline date wait; it uses `pressContinue` (it must leave the CFO's proposal unanswered). m4b already waits on the advance response (PR #23).
  - Cloud sessions run `make e2e` with `PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium` (the pinned Playwright's headless shell is not installed here).

## Follow-ups

- M16: findings 2 and 3 (consolidation membership by period; ultimate ownership for antitrust and finance).
- The exit sale's `Acquisition` exists before the company is the buyer's brand (between acceptance and Found again or Retire); M16's group model may want ownership from the acceptance month.
- `api/rival_views.staff_estimate` and `deals.public_costs_cents` compute the same displayed headcount separately; one helper would keep them in step.
- Hardware's unit-cost arithmetic (BOM, plants, contracts per unit) is still float before it rounds to cents; only the stored contract price is exact now.
