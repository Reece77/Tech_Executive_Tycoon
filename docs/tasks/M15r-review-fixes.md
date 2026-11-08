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
- **Exact money** (finding 8): `deals.cash_part_cents` (Fraction, half-even once); the other M&A helpers multiply in Fractions (`money.exact`). Contract prices are integer millicents (`price_millicents`, migration `0037_m15r`; quantized at signing); the sim reads `price_cents` as a property.
- **Playtest 4 addendum** (Reece, 2026-11-08; `docs/playtests/reece-playtest-4.md`), each with a regression test:
  - **(a) Negotiation:** an offer at or above the target's reservation is accepted in any round, before the lowball and round checks; a counter is never below the offer it answers (`_counter` holds it above the offer on its own). The bug: each round halved the gap to the reservation without regard to the offer, so $17.9M was countered at $17.0M. A consequence: when a counter is more than 1/`mna.lowball` (1.11x) above the reservation, any offer that is not a lowball is above the reservation and is accepted, so rounds run only while the counter is within that band. Tests: `test_a_counter_is_never_below_the_offer` (failed before the fix), a Hypothesis property over offers below the reservation; the rounds and lowball tests now bid below the reservation.
  - **(b) Rankings news:** the item names the player's place on each of the three lists ("not ranked" when absent) and each list's top `rank.news_top` (5, in balance.yaml) names, and carries `link_kind` `rankings`, which the inbox shows as an Open Rankings button to `/competitors/rankings`. No schema change (`inbox_item.link_kind` is a string). Tests: `test_the_news_item_names_each_lists_top_and_links_the_screen`; e2e `m15b.spec.ts` (c) opens the item and follows the link.
  - **(c) Africa:** Lagos (pay 0.35x, rent 0.30, talent weight 2, business +0.3), Nairobi (0.35x, 0.20, 2, finance +0.5) and Cape Town (0.45x, 0.30, 1, technical +0.3), appended after Sydney. Pay sits below the region's 0.55x as Bangalore and Sao Paulo sit below theirs; rents between Bangalore's and Sao Paulo's. `home_city_region: africa: europe` stays, so people saved with no city of their own keep London and their pay. Goldens unchanged (their worlds draw no relocator or "anywhere" candidate whose city the new weights move). Tests: `tests/unit/test_m15r_africa.py`; the M9 table test now counts 18 cities.
  - **(d) The AI lab:** goal kind `arr` ($100M ARR, judged early as before, deadline December 2020) replaces `era_or_arr`; `GoalSpec.bonus_era`/`bonus_text` describe the bonus, `scenarios.bonus_reached` reads it from the era arrivals when the result screen asks, and it is never judged. The result screen shows "Bonus: Cause the Transformers era first." and whether the company did it. Tests: `test_the_ai_lab_wins_on_arr_and_transformers_is_a_bonus` (Transformers first alone neither wins nor ends the game).
- **Migration number**: written as `0036_m15r` on `0035_m15b`; renumbered `0037_m15r` on M15a's `0036_m15a` at the merge (and again onto M24's if it lands first).

## Follow-ups

- M16: findings 2 and 3 (consolidation membership by period; ultimate ownership for antitrust and finance).
- The exit sale's `Acquisition` exists before the company is the buyer's brand (between acceptance and Found again or Retire); M16's group model may want ownership from the acceptance month.
- `api/rival_views.staff_estimate` and `deals.public_costs_cents` compute the same displayed headcount separately; one helper would keep them in step.
- Hardware's unit-cost arithmetic (BOM, plants, contracts per unit) is still float before it rounds to cents; only the stored contract price is exact now.
