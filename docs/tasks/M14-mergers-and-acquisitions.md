# M14: Mergers and acquisitions

**Goal:** buying companies is a real strategic lever. Any company can be bought, from a struggling startup to a listed incumbent, for cash or (once listed) stock, by friendly offer or hostile tender. Due diligence narrows what you know. Regulators block deals that make a market too concentrated. After each deal you choose: keep it as a brand you steer with a directive, or integrate it for savings at the cost of culture clash and departures. Rivals buy startups too, and a bid for your own company can now end the game with an exit.

**Spec sections:** §2 (v2 fantasy), §10 (instruments) · **ADRs:** 0002, 0003, 0004, 0013 (streams `mna` 37, `integration` 38, `rival_mna` 39), 0015, 0019 (§16), 0020 · **Formulas:** `docs/formulas.md` §28 (all), with §15, §20.3, §25, §27 · **Depends on:** M13b (`m13b-done`) · **Lane:** A, alongside M14b

## Lane

- **Lane A.** It runs at the same time as M14b (lane B, people and press) in its own session and branch (`m14-mna`).
- **Merge order: M14b merges first.** Before merging M14: merge `main` (with M14b), re-parent M14's unmerged migrations, add M14b's press trigger for an acquisition announcement (§29.1) if M14b left a hook for it, regenerate golden snapshots once with both milestones' reasons in CHANGELOG, and re-run every guard on the combined code. If an M14b target moves, report it rather than tune M14b's keys.
- **M14 owns:** new `backend/tst/sim/mna/`; rivals' startup purchases; consolidation in finance; `listed_from` in `incumbents.yaml` and `entrants.yaml`; account 1800; `data/events/deals.yaml`; the Rival screen's value and deal controls; Finance → Deals and subsidiaries; Org's acquired units and directives; the exit ending.
- **M14 must not edit:** `backend/tst/sim/press/`, the rival CEO and feud code, `hiring/` recruitment changes, `data/events/press.yaml`, the Recruitment screen or the Overview's credibility panel (M14b's).
- **Shared files:** `balance.yaml` (add only `mna.*`, `antitrust.*`, `integration.*`; both lanes append to `events.trigger`), `docs/formulas.md` (notes in §28 only), `RivalScreen.tsx` (M14 owns it; M14b adds one panel component), `CHANGELOG.md`, `docs/data-dictionary.md`: keep both sides.
- **RNG:** `mna` 37, `integration` 38, `rival_mna` 39; lane B has 40–42.

## Design for v3 (ADR-0020)

- A brand subsidiary is a company with `parent_id`: its own ledger, pools, people and decisions. M16 adds cap tables, boards and minority stakes to the same model; do not add them now.
- Every function takes a `company_id`; consolidation iterates `player_companies(state)` extended with subsidiaries (one helper, `group_companies(state, parent_id)`).
- Rivals and the player use the same deal code (§28.6).

## Out of scope

Minority stakes, subsidiaries' own boards and cap tables, spin-offs and selling a division (M16). Goodwill impairment (follow-up). Earn-outs. Rivals bidding for each other's listed companies (rivals buy startups only).

## Sub-tasks (commit after each)

1. **Data and formula tests:** `mna.*`, `antitrust.*`, `integration.*` keys in `balance.yaml` with comments; `listed_from` for incumbents and entrants following history; account 1800 goodwill; the three streams in ADR-0013's main table (keys: stable rival keys); every §28.10 worked example as a unit test.
2. **Valuation** (§28.1): `V_f` for every company, listed rivals' market cap and sentiment, private value ranges with the seeded offset. **Test:** a company that never buys plays exactly as before (golden snapshots unchanged by this sub-task; valuation is read-only).
3. **Diligence and offers** (§28.2–28.3): diligence and hidden problems, private and listed offers, counters, hostile tenders, financing (cash, stock, a loan first), closing with goodwill.
   - **Property tests:** the ledger balances through closing (cash, stock and mixed consideration); the cap table sums to 100% after a stock deal.
   - **Differential test:** two targets with the same displayed range but different true values give the same API responses before diligence (no oracle in errors or ordering, as M12r finding 1).
4. **Antitrust** (§28.4): combined share by market, review, block probability, remedies with divestiture. Deterministic block test; seeded review test.
5. **After closing** (§28.5): the brand subsidiary (consolidation, cash sweep, directive, moving key people) and integration (products, key people, pool staff to individuals with the cap, severance, culture clash, flight, churn, technology). Tests for each, and a turn-time check: integrating the largest incumbent keeps `test_product_perf`'s budget.
6. **Being acquired and rivals' deals** (§28.6): accepting a bid ends the game with the exit ending; rivals buy startups.
7. **Pitches** (§28.7): the acquisition kind for the CEO and CPO; never auto-approved.
8. **API, CLI and screens:**
   - **Rival screen:** value (market cap or range), Diligence and Make an offer buttons, deal status.
   - **Deals panel** (Finance → Deals): open offers, reviews, closings, integration progress.
   - **Finance:** subsidiaries' columns and the consolidated statements; goodwill on the balance sheet.
   - **Org:** acquired units, flagged for 12 months; a directive control on each subsidiary.
   - **Exit ending** on the Game over screen.
   - **CLI:** `tst targets`, `tst diligence --company`, `tst offer --company --price --cash-share`, `tst directive --company --mode`.
   - **Hidden values:** extend the hidden-value test to §28.8's list.
9. **Balance and e2e:**
   - §28.9 targets printed and recorded; add the "acquirer" arm to the balance scripts; tune only `mna.*`, `antitrust.*` and `integration.*`.
   - **Playwright:** (a) diligence then a friendly offer for a startup, then integrate it and see its people join; (b) buy a startup and keep it as a brand, set a directive and see the consolidated P&L; (c) a scripted deal over 50% combined share is blocked and the remedy offered; (d) accept a takeover bid and see the exit ending.
   - **No new xfails;** any guard that fails against `main` and that M14's keys can't fix is reported with values, and you stop before merging.
   - Close-out: CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every §28.10 worked example passes as a test.
- [ ] A company that never buys plays exactly as before.
- [ ] Deals close with a balanced ledger and a correct cap table (property tests); no hidden value reaches the API or a prompt (differential and hidden-value tests).
- [ ] Antitrust blocks over 50% without a remedy; brand and integrate both work as specified.
- [ ] §28.9 targets 2–7 met (printed, values recorded); target 1 holds.
- [ ] `test_product_perf` stays within budget.
- [ ] `make check` green; `make e2e` passes; merged after M14b with migrations re-parented, golden snapshots regenerated on the combined code and both milestones' guards passing; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m14-done`.

## Manual check (Reece, after merge)

On `pt-ipo` after listing, buy a struggling startup in your category and integrate it, then buy a second one and keep it as a brand with the "grow" directive. A year later: who left, what did integration save, and does the brand pull its weight? Then try a deal that crosses 50% of a market.

## Status (2026-11-05, after the product manager's ruling on target 4)

Sub-tasks 1-9 are built and tested; every §28.9 target is in band (values in `docs/balance-targets.md`, M14):

| Target | Value | Band |
| --- | --- | --- |
| 2 private deals / listed premium | 1.37 x V_f / 35% | 1.0-1.6 / 25-50% |
| 3 key people lost: integrated / brand | 25% / 0% | 10-30% / <= 10% |
| 4 payroll cut by integration (every integrated deal) | 24% (scripted 23%, the acquirer's startups 52%) | 15-35% |
| 5 acquirer / steady + regions ARR, year 10 | 1.05 | 1.0-1.4 |
| 6 deals at 40% blocked after review, after 2020 | 40% of seeds | 15-50% |
| 7 incumbents' startup purchases a decade | 2 (median) | 1-4 |

## Decisions made

- **Fees** (diligence, failed tenders) post to 6900 general and administrative; 28.2's "6100 professional fees" names an account the chart does not have (6100 is rent).
- **Accounts.** 1800 goodwill, and 1810 investment in subsidiaries for a kept brand's book equity (consolidation replaces it with the brand's net assets; cash sweeps reduce it).
- **Hidden problems** are fixed per target from the master seed (stream `mna`, turn 0), equivalent to "drawn when first looked at" without depending on what the player opens.
- **Mode** (brand or integrate) is chosen with the offer and can change until closing; final at closing; integrate by default. A deal agreed in a month closes at that month's end.
- **Counters** are whole dollars (rounded up), and once made they are the bar: a lower offer ends talks even if it clears the hidden reservation.
- **Displayed value ranges** are rounded outward to two significant figures, so the display is no oracle (the differential API test relies on it).
- **The remedy** divests the target's overlapping product, not the acquirer's.
- **Integration (product manager, 2026-11-05).**
  - Each acquired product keeps its revenue share of the target's staff; by function, sellers and marketers are let go at `integration.synergy_overlap` (0.40) where the acquirer already sells in the category, `synergy_new` (0.15) otherwise; builders at `synergy_builders` (0.10); key people in other functions at `synergy_other` (0.30), the lowest paid first. This replaces the maintenance-line rule; `max_per_product` is gone.
  - Kept pool staff keep the pool's pay (the function role's mid rate), so a saving is people let go, not a pay change.
  - Only targets with at most `integration.max_staff` (250) staff integrate. The limit is checked at the bid, at a mode change and at closing (a target that grew past it becomes a brand). The Integrate control is disabled with the reason, rivals buy only startups within it, and an acquisition pitch proposes a brand for a larger target.
  - Target 4 is measured on payroll over every integrated deal (scripted deals integrate only targets within the limit); the synergy keys land it in band untuned.
  - The perf checks: Apple bought as a brand (211 ms a turn) and Facebook, the largest target within the limit (219 staff), integrated (644 ms a turn); limit 1 s.
- Key people spread over the new units in employment order.
- **Culture distance** comes from the companies' average personality traits (`integration.distance_span` 4 points = distance 1). `integration.clash` is 0.1, a new key for 28.5's clash.
- **Flight, clash and sweeps** start the month after closing; flight is tracked for the player's acquisitions only.
- **The exit:** talks queue a `takeover_offer` event (data/events/deals.yaml) for the next month; accepting sells to the largest rival by revenue at the bid's premium; the game outcome is `exit`. `tst offer` keeps `--candidate` for job offers and takes `--company --price` for bids.
- **Pitches:** two new keys, `mna.pitch_synergy` (0.25) and `mna.pitch_bid_premium` (0.30), for the pitch's central case and its bid.
- **Rivals' purchases** need the combined share below the review line, close in the same month and merge the startup's pools into the buyer's.
- **Storage:** M&A records keep their fields as JSON (migration 0033); kept brands' parents are in `company_parent`.
- **Tuning (28.9):** `integration.flight_brand` 0.007, `integration.flight_base` 0.01, `mna.rival_rate` 0.005 (0.008 until the lane merge; see below).

### Lane merge with M14b (2026-11-05)

- `0033_mna` became `0034_mna` on top of M14b's `0033_press` (schema version 34).
- M14b's hooks are called from `mna/deals.py`: an agreed deal queues an `acquisition` press moment for the acquirer (`press.queue_moment`; only the player has moments), and the player's hostile tender adds `feud.hostile_bid` (20) to the feud with the target's CEO, whether it succeeds or fails (`characters.add_feud`, cause "you made a hostile bid").
- `mna.rival_rate` 0.008 -> 0.005: M12a's living-market guard (`test_1_living_market_launches`, at least 1.0 launch per v1 category a decade) read 0.97 with M14 (39 of 40 launches; `main` reads exactly 1.00, and 1.00 with rival deals off). Rival purchases close startups that would have launched. The guard is not monotonic in the rate (0.004 and 0.006 also read 0.97), because `main` sits on the floor; 0.005 passes, and every 28.9 target stays in band (table above, re-measured at 0.005).

### Before merging: lane B's files and Reece's playtest 3 (product manager, 2026-11-05 and 2026-11-06)

- **Known misses test.** `test_known_misses` covers only the balance table's own targets; a milestone-prefixed miss (`M10.T3`) is measured and xfailed in its own milestone test (`test_m10_balance.py`) within the same bound. Before, it failed on `main` with "no M10.T3 row".
- **Group companies are not rivals** (`rivals/characters.py`, open to lane A now M14b has merged). A player's company and its kept brands (`in_player_group`, from `parent_id`) never feud, speak, jab or count for head-to-head launches; `add_feud` ignores them. Any feud with a company resets to 0 when it closes as an acquisition (`reset_feud`; its causes stay as history).
- **Acquisition moves are not poaching.** Integration ends a key person's job with reason `acquired`, which the feud's poaching check skips; taking a kept brand's key person through the Poach channel also ends their job as `acquired` (`poaching.leave_rival`), so History and Former staff do not call it poaching.
- **Antitrust (playtest 3 card 4).** Reproduced on `tools/e2e_m14_save.py blocked`: the engine blocks the Zoho offer (combined share 99-100% in B2B SaaS, SMB, North America, at once and after 1, 3, 6 or 12 months), and then Salesforce (100%, after the remedy and closing). What failed was the message: the answer and the inbox led with "Deal agreed: Zoho" and named the block only in the detail. Now the title leads with the outcome ("Deal agreed, but blocked by antitrust: ...", "Deal agreed, pending antitrust review: ..."), and every agreed deal of the player's, including a re-screen after a remedy, gets its own screening note: "cleared: no overlapping market", cleared under the 35% review line (with the share and market), under review, or blocked with the remedy. Notes name the public review and block lines, never a review's block probability or its drawn outcome. Antitrust markets are a category, segment and region (28.4), so a large share of a category spread over segments the player does not sell in clears.
- **Brands' cash (playtest 3 card 2).** Each month after sweeps, a parent pays a brand's cash shortfall up to `mna.funding_months` (1) of the brand's monthly costs and what the parent has: the parent's 1810 investment and the brand's equity rise by the amount (the mirror of a sweep, balanced in both books). A brand with an operating loss for `mna.loss_warning_months` (3) months running since closing raises one inbox warning per losing streak. A brand never counts insolvent months while its parent's cash covers its shortfall; a brand whose parent cannot pay fails as any rival.
- **Rival screen (card 1).** The Products panel lists each product's market: category, segments and regions (`products` on the rival profile; home-market segments sell in the home region, as antitrust counts them).
- **Inbox link.** The top bar's "Answer 1 event first" opens the first event that needs answering (`/events/<id>`), not the inbox.

### Turn time at about 220 staff (product manager, 2026-11-06, option 1)

The integration perf check (Facebook, 219 staff, integrated) failed `check` twice under CI load (1.69 s and 1.41 s a turn).

- **Where the time went** (alone, this 4-core machine, one turn after warm-up: 820 ms; profiled with cProfile and timed per phase without it):
  - All 190 remaining staff sit in one unit, so the company tracks 18,145 relationship pairs, of which about 1,400 change in a month (the rest sit at their start value).
  - The turn (374 ms): morale 108 ms (W_rel read every unit-mate for each person; teammate tags read every unit-mate's tags; each person's morale rebuilt the whole person-state tuple), relationships 62 ms (every pair rebuilt and replaced; the pair map rebuilt 13 times).
  - The save (295 ms): relationships 107 ms (all 18,000 pairs diffed, an ORM row per change, a DELETE per ended pair), rivals' monthly operating history and the M&A records a `session.merge` (a SELECT) per row.
  - Outside the turn: full (generation 2) garbage collections of 250-580 ms every few turns, and the test helper `answer_critical` reloading the whole save from disk (0.7-1 s) in months with a critical event.
- **What changed** (identical results):
  - Relationships stay within units and to managers; the pair set is remembered while the org is unchanged; a month removes ended pairs, merges in new ones and steps only pairs that are pushed or off their start value (carried from last month); unchanged pairs and an unchanged tuple are reused, so the caches and the save see no change.
  - W_rel and the teammate tag terms in bulk: every person's unit-mate values in one pass over the pairs in key order (the same order `teammates` gives, so sums match); each unit's tag counts once per view. The relationship map is built once per pairs tuple. Morale's person-state updates are applied once after the loop (morale reads only the person's own state).
  - Reveal narrowing computes its shrink factor once per action; the city pay multiplier is remembered.
  - The save writes only rows that changed, in batched statements: relationships by position (an executemany of plain rows; ended pairs one batched DELETE), rivals' histories and the M&A records as one UPDATE per table, unchanged people and rows skipped by identity.
  - The test helpers `answer_critical` and `answer_events` read the remembered state through `read_session`, as the app's screens do.
- **Proof of identical results:** the golden snapshots are unchanged (golden seed 1 runs with `TST_STATE_CACHE_CHECK=1`); the 219-staff scenario played 12 turns with the state-cache check on gives the same full-state digest on the old and new code; `tests/unit/test_turn_time_same_results.py` (Hypothesis) checks the step, W_rel and the tag terms against the rules as first written while people move, leave and join (a deliberately broken step fails it).
- **Timing tests** (marker `timing`): `test_product_perf`, the two M14 perf checks, and the three other 1.0 s budgets of the same kind (`test_org_perf`, `test_hiring_flow::test_turn_time_budget`, `test_rival_balance::test_5_speed`) run in their own step, `make check-timing` (`pytest -n 0 -m timing`), after the parallel suite: in CI as a step of shard 1 of `check`, locally at the end of `make check`. The limit stays 1.0 s.

| Alone, this machine (median of three blocks) | Before | After |
| --- | --- | --- |
| Integrate Facebook (219 staff) | 905 ms (blocks 941, 844, 905) | 555 ms (555, 559, 531); 541-558 over three runs |
| Buy Apple as a brand | 289 ms | 256 ms |
| test_product_perf (120 turns) | 367 ms | 308-333 ms |

On CI (`make check-timing`, shard 1 of `check`, af1d7dc), green on both runs, the push run and the pull request's run: the 219-staff integration 544 ms (blocks 573, 536, 544) and 567 ms (586, 550, 567); Apple as a brand 284 and 289 ms; test_product_perf 337 and 340 ms; the step's six tests in 3 min 46 s. Before, under the parallel suite: 1.69 s and 1.41 s (failed).

## Follow-ups

- Goodwill impairment (out of scope).
- The acquirer's own overlapping product as a remedy.
- Rivals' executives pitching acquisitions; rivals bidding for the player outside the takeover event.
- A Deals entry in the top bar when a review or a closing is due.
- M15a: turn time beyond 220 staff. Full garbage collections (250-580 ms at 220 staff) grow with the state's object count; `gc.freeze()` after each turn measured 50 ms better on the block mean but is not adopted (frozen cyclic garbage would never be freed). Reveal narrowing rewrites about 6,900 rows a month at this size.
