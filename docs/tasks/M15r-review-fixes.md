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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
