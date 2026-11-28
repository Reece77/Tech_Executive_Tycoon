# M57r-A: Review 10's engine fixes (lane A)

**Goal:** close every review 10 finding owned by lane A: stable RNG keys, exact money, a bank that can't run on negative cash, and the cross-system bugs in currencies, finance, media and the editor. **No new features.**

**Findings:** `docs/reviews/review-10-consolidated.md`, items **5–18 and 28–30** (with the reviewers' own files `codex-review-10.md` and `review-10.md` for detail and reproductions) · **Rulings:** the consolidated file's "Product manager rulings" 3, 4, 5 and 7 · **ADRs:** 0002, 0003, 0013, 0025 · **Depends on:** `m59-done` · **Lane:** A, alongside M57r-B

## Authority

CLAUDE.md §9 asks a session to stop on a P1 defect. These P1s (items 5–8) are already reported and ruled: **fix them; don't stop for them.** Stop only for a new P1 the reviews didn't name.

## Lane

- Its own session, in its **own clone or worktree**, on branch `m57r-a` from `main`.
- **Owns:** `backend/tst/sim/**` except `tst/sim/negotiation/`, `tst/sim/talks/`, `tst/sim/meetings/` and `tst/sim/media/talent.py` (lane B's); `backend/data/**`; `tests/money_guard.py` and its test; `tst/history_coverage.py`; `tst/sim/modes/custom.py`; ADR-0013; the `determinism` workflow's digest list.
- **Must not edit** lane B's files: `tst/conversations/`, `tst/api/`, `tst/desktop/`, `tst/db/`, `tst/profile/`, `packaging/`, `.github/workflows/release.yml`, `tst/balance/known_misses.py`, the conversation and meeting tests.
- **No fixed merge order:** the first ready merges first; the other merges `main` and re-records what it must.
- CLAUDE.md §9's decision rules apply.

## Sub-tasks (commit after each; each with the test named in the finding)

1. **Stable RNG keys** (item 5, ruling 3):
   - auctions by market key and year;
   - banks by owner, region and a local ordinal;
   - FX and world streams by region **key**;
   - the editor's added rivals by category key;
   - robotaxi incidents by zone and turn;
   - `_year_share` summed in sorted order.

   **Insertion tests:** add an unrelated auction, bank, region-file reorder and category reorder, and every existing entity's draws are unchanged. Correct ADR-0013's rows, including the unused fraud stream and the catastrophe key with its month.
2. **Exact money** (items 7 and 8):
   - integer ceiling division for clock prices;
   - rational capex throughout the quote;
   - `round_half_even` for custom rival cash;
   - each month's interest, charge-off and float income as one rational expression;
   - claim cohorts that clear completely;
   - streaming licences and every per-month split of a yearly amount by cumulative entitlement.

   **Money guard:** add the aliases `price`, `cash`, `value`, `premium(s)`, `deposit(s)`, `loan(s)`, `notional`, `claims`, `budget`, `balance` and `capex`, and triage every hit. **Tests:** half-cent boundaries, and a reserve that reaches zero when claims stop.
3. **Bank liquidity** (items 6 and 9): ordinary outflows and runs settle through one liquidity routine that sells securities at market value (loss to 4530), then restricts, then fails the bank. Charter capital can't be withdrawn before the charter or below its minimum. **Property test:** `reserves_cents >= 0` every month, with the books reconciled to account 1060.
4. **Currencies against engine prices** (items 10–12, ruling 4):
   - FX marks resolve after dynamic pricing;
   - engine-priced segments re-mark every month;
   - royalties, claims and fees are taken from booked revenue;
   - `FxMonth` revenue is built from what was booked;
   - several settlements are summed, with gains and losses posted separately and a row for a settlement-only month.

   **Tests:** `FxMonth` revenue equals ledger revenue for a unit-sale line abroad; three forwards settling in one month match the ledger on the Currency screen's data.
5. **Finance and media timing and pricing:**
   - finance's demand and dated caps before sales (item 13);
   - ad calibration with no sellers priced from digital spend (item 14);
   - privacy cuts weighted by where impressions are delivered, with iOS share from M31's state (item 15);
   - game store fees through `platforms.data.fee_for` to the owner (item 16, ruling 5);
   - a charter moves with an integrated or sold bank or insurer line (item 17);
   - the editor refuses starting customers in gated families (item 18).
6. **History, Windows parity and turn 0:**
   - the loader validates monthly and annual series' continuity (item 28);
   - a poisson-heavy seed joins the `determinism` digests, with a `dmath` sampler if Windows differs (item 29, ruling 7);
   - `x if x is not None else …` at every `or turn` site, with a grep guard;
   - `began_in` uses the save's start month (item 30).
7. **Close-out:**
   - re-record every fixture and state cache whose numbers move, each with its reason in the CHANGELOG (RNG keys and rounding change outcomes);
   - re-run every earlier guard and the nightly on the branch (rule 7). Guards moved by these fixes are M57's to retune: record each reading, as M46 did, but don't add known misses (lane B owns `known_misses.py`);
   - fill in the consolidated file's Resolution column for items 5–18 and 28–30 (status and commit).

## Acceptance criteria

- [ ] Every lane A item is fixed with its test, or explained in "Decisions made".
- [ ] The extended money guard has no unexplained hit; the insertion tests pass; the bank's reserves are never negative.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged with `Milestone-Tag: m57r-a-done`.

## Decisions made

(filled in by the session)

## Follow-ups

(filled in by the session)
