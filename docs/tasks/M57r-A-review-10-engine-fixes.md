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

Built on branch `claude/m57r-a-engine-fixes-597pvg` (the session's assigned branch, in place of `m57r-a`), in its own clone.

1. **Stable keys (item 5, ruling 3).** `tst.sim.rng.text_key(key)` (the first 48 bits of the data key's BLAKE2b digest, pinned by a test) turns a data key into a key part. Auctions draw on `(1, text_key(auction key), year)`: the auction's key names its market (telecom.yaml's key, or `seeded_<region>_<area>_<n>`), and the year is the ruling's; seeded schedules use `text_key("region/area")`. Banks: `(*owner's stable key, text_key(region), ordinal among the owner's banks there by id)`. FX, world cycles and M53-M55's growth and catastrophe streams key by `text_key(region)`; media growth also by `text_key(category)`; the editor's added rivals by `(1_000_000, text_key(category), k)` with rival key `(20, text_key(category), k)`, entering in category-key order. A robotaxi incident's talk subject is `incident_key` = zone x 2^33 + `turn_key(month)` (one edit in lane B's `tst/sim/talks/opening.py`: the brief assigns the item here). Older streams keyed by region or category index (market, commodity, power, region_risk, vehicles, robotics, pharma, dynasty) and media's `(2, region index, year)` in lane B's `talent.py` are unchanged (ADR-0013 amendment; follow-up).
2. **Clock and capex (item 7).** `next_price` is integer ceiling division over the increment's exact decimal; the player's bid limit enters the clock as its integer. Network capex is a Fraction through the quote (`radio_exact`, `civil_exact`); `radio_cents` and `civil_cents` stay floats for the API.
3. **One rational expression a month (item 8).** `money.times_over(amount, divisor, *rates)`: bank loan, reserve and deposit interest (all loan kinds summed then rounded once), charge-offs, partner fees, insurer float income and payments' monthly volumes. A streaming licence's month is the difference of consecutive rounded cumulative entitlements (`licence_month_cents`).
4. **Claims cohorts (item 8).** No cohort records (that would be a schema change in lane B's `tst/db`): a line's reserve pays `ceil(reserve / lag)` a month, so it clears completely once claims stop (a 1-cent property reserve pays the next month). The lag's mean is unchanged to within a cent.
5. **Money guard (item 7).** The 17 aliases added (with plurals `prices`, `values`, `budgets`, `balances`) gave 91 hits: 12 fixed (automation's price steps, equipment's prepayment, activist buybacks and settlements, PPAs' monthly and minimum amounts, a mine's spot cost, a refinery's transfer, the world's chain revenue and opening books), 78 triaged with a `money-exact:` reason (scores and attributes named `value`, unit rates, rival estimates, integer products the scanner reads as float), and 1 deferred: lane B's `tst/sim/talks/opening.py:358` (a trait weight) in `DEFERRED`.
6. **Liquidity (items 6, 9).** `banks.pay_out` settles ordinary outflows and runs alike: reserves, then securities at market value (loss to 4530); an outflow it cannot pay fails the bank. Forced sales for an ordinary outflow set `restricted` (the existing rule lifts it the same month once capital is at its requirement, so it bites only on a weak bank). Costs that would leave reserves negative are met by sales or fail the bank. Inflows and outflows are posted as two entries ("Bank deposits in", "Bank deposits out"). Charter capital: no withdrawal before the charter, none below `charter_capital_cents`.
7. **Currencies (items 10-12, ruling 4).** FX marks are taken after media's `open_month` (ad prices). Engine-priced lines (`media.ads.engine_priced`: social, ad-priced apps) re-mark every month. Royalties (`monthly_revenue_cents`), insurance premiums and claims, and store-fee bases read `translate.booked_price`. `FxMonth.revenue_cents` is phase 5's booked revenue by (company, region) (`MarketOutcome.booked_by_region`); settled forwards are summed, a settlement-only month has a row, gains post to 4940 and losses to 4945 in one entry. M54's balance script passes its booked revenue (a script fix, decision rule 2).
8. **Finance timing (item 13).** `finserv_phase.open_month` (growth draws, demand, the history pin) runs first in phase 5; phase 9 keeps networks' acceptance and the month-end pin.
9. **Ad calibration (item 14).** A region is calibrated once, at the first month anyone sells ads there (`media.start` for regions with sellers, unchanged); a later calibration's price is digital spend / impressions offered, capped at the history's price. Until then the history's price stands. Saves already holding a 1e-9 reference keep it (follow-up).
10. **Privacy (item 15).** ATT cuts targeting x iOS users not on the company's own platform (M31's `platform_regions` share of the `ios` platform; media.yaml's `ios_share` only before M31's platforms exist); regional rules x users not on the company's own platforms.
11. **Game store fees (item 16, ruling 5).** The mobile part pays each M31 device store's schedule (`platforms.data.fee_for`, which now treats a category without an app profile, games, as purchases), weighted by users and region market sizes, to the owner: nothing on the seller's own store, 5900/4300 inside the group, 4150 to an owner in the game, 5150 against cash outside it. PC and console keep media.yaml's fees (no M31 stores).
12. **Charters (item 17).** `finserv.charters`: integrating a rival's banking line gives the acquirer a partner-bank programme in each region it serves (rivals' charters are not records); an insurance line arrives with active licences (the player capitalises the insurer). An ordered sale takes the seller's banks or insurer once no line of the kind is left, the books out to 4930.
13. **Editor (item 18).** Starting customers are refused in mobile, fixed broadband, wholesale, banking, insurance and payments lines; such a line may start with none.
14. **History (item 28).** A series is annual (monthly) when 75% of its steps are one; such a series may not miss a year (month) from its first entry to 2010 (January 2010). Anchor series interpolated later are sparse; gaps after 2010 are not M50's guarantee.
15. **Poisson parity (item 29, ruling 7).** No seeded game draws a mean of 10 or more early (the 2030 dynasty start's largest in 13 months: 3.5), so the `determinism` job gains a `poisson/42` probe: 120 "months" of 16 draws at eight means (10 to 3.3e7) on the engine's stream derivation (`misc`, key (57, i)). Result: see the readings below.
16. **Turn 0 (item 30).** 19 `x_turn or y` sites became `is not None` tests; `tests/unit/test_m57r_a_turn_guard.py` fails on any new one. `began_in` uses the save's start month for any mode begun before 2010 (a later start stays as M50 left it).

17. **Readings (sub-task 7).** The nightly on the branch (run 46117717617, at 680fa80, before the fixtures were re-recorded): every balance guard holds but one. **M54.T5** (an 80% hedge's cut of yearly profit's spread, target >= 15%, known miss bounded at a 10-point shortfall) reads a **3.3%** median cut against M54's 6.9%, a shortfall of 11.7 points, past its bound: the FX walk is now keyed by region key (item 5), so its seeded path differs; the hedging script's booked revenue is unchanged. It is M57's to retune with the target's 24-month-forward decision; no known-miss row is changed here (lane B owns `known_misses.py`). `M22.T2.variant` reads 10.6-21.0% (inside its known-miss bound) and `M13b.T1` 6/10 seeds (known). The other nightly failures were the fixtures since re-recorded (M30's state cache, M37's reference, M28's history). M30's re-recorded cache shows `integrator/3` going bankrupt at month 284 (360 before). `check`, `check (timing)`, `e2e` and `determinism` green on the PR head.

## Follow-ups

- Re-key the older region- and category-index streams (market, commodity, power, region_risk, vehicles, robotics, pharma, dynasty; media's `talent.py` region draw, lane B's file) by `text_key`, in one milestone that re-records everything once.
- Claims cohorts as records (a migration) if the ceiling-paid reserve's timing matters for balance.
- A save holding an ad reference calibrated on no sellers keeps the 1-cent price: a migration step could drop such references.
- Lane B: annotate `tst/sim/talks/opening.py:358` and remove its `DEFERRED` row in `tests/unit/test_money_guard.py`.
- Older per-month splits of yearly amounts outside the review's range (regulation's compliance cost, M28's chain books) by cumulative entitlement.
