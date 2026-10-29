# M5: Rivals

**Goal:** the market fights back. The 2010 incumbents get people, ledgers and a personality, and decide every month whether to cut prices, push features, quality or brand, enter segments, cut costs or poach the player's best people; rival startups are founded, raise, launch and die; the player can poach from rivals; and a Competitors screen shows it all. One milestone: rules, API, CLI and screens.

**Spec sections:** §9, §10, §13 · **ADRs:** 0002, 0010, 0013, 0015, 0017, 0018 · **Formulas:** `docs/formulas.md` §15 (all) and its §12 rows · **Wireframes:** `docs/wireframes.md` (M5 screens) and `docs/wireframes/source/Competitors.dc.html`, `Rival.dc.html` · **Depends on:** M4c (`m4c-done`)

## Context

Until now the incumbents held fixed scores (ADR-0017), so a player could learn the market once and win it. M5 makes every rival an ordinary company run by the same rules as the player, with decisions from a utility AI in phase 2 (ADR-0010, ADR-0015). `docs/formulas.md` §15 is authoritative.

## Out of scope

M&A and acquisitions (v2; the acquirer personality is not used), rival fundraising beyond §15.4's simple rule, rival R&D trees (v2), events and storylines about rivals (M6), rival screens beyond the two wireframes.

## Sub-tasks (commit after each)

0. **Faster tests:** add `pytest-xdist` (approved, ADR-0001) to the dev dependencies; run the backend suite with `-n auto` in `make check` and `make check-fast`; make any test that shares files or ports parallel-safe. Record the before and after run times.
1. **Data and formula tests:** `incumbents.yaml` gains personality, builder skill, target margin and cash months (§15.1); a company-name pool in `names.yaml` for startups; all §12 M5 keys; every §15.8 worked example as a unit test.
2. **State and persistence:** rival workforce pools, key people (as persons with employment at the rival), rival ledgers, pushes and cooldowns, poach approaches, rival startups; migration; data dictionary. Older saves: incumbents get pools sized per §15.1 at their current revenue, key people generated, cash at the table's months of revenue.
3. **Rival economics:** pools sized from revenue, payroll, hosting and marketing in phase 6, revenue in phase 5, bankruptcy (§15.1); property tests: every rival ledger entry balances, pools never negative.
4. **Rival decisions** (§15.2, §15.3): utility, personality weights, cooldowns and pushes, action effects, `decision_log` with `source = "rival"`, replay by recomputation.
5. **Rival startups** (§15.4): founding, individuals and product development under §11, funding, bankruptcy, released people.
6. **Poaching** (§15.6): rival approaches with the counter window and phase 1 answer; the player's "Poach from a rival" channel with the leaving penalty and the quality hit.
7. **API and CLI:** rivals list and profile (personality, estimated headcount, products with public scores, cash label for incumbents ("deep pockets", "comfortable", "tight") and nothing for startups, recent moves, key people with the player's revealed ranges), market news, approaches (with a counter-offer preview showing the new chance band, not the probability), poach searches; `tst rivals`, `tst rival --id`, `tst news`, `tst poach --rival`. Extend the hidden-field test (no utilities, needs, noise, true attributes of key people, or acceptance probabilities).
8. **Screens:** Competitors (nav key 8, now live) and the rival profile per the wireframes; the approach item in the inbox with Counter (opens the raise dialog with the chance band) and Let them go; the Poach channel card on Recruitment; a News kind badge.
9. **Golden, balance and e2e:** regenerate golden snapshots (rival moves change markets; CHANGELOG note); print the §15.7 balance table and tune only `rivals.*` keys and personality weights until it holds; record values. Playwright: (a) open Competitors and a rival profile; (b) receive a scripted approach, counter it, and see the answer at Continue; (c) poach a rival's key person through the new channel.

## Acceptance criteria

- [ ] Every §15.8 worked example passes as a test.
- [ ] Incumbents act: a scripted share loss makes a cost leader cut its price and a premium rival start a push, and both show in Market news.
- [ ] Rival startups are founded, launch, raise and fail across 120 turns, within the cap of 8 alive.
- [ ] Rival approaches arrive, can be countered, and resolve per §15.6; the player can poach a rival's key person, and the rival's product loses quality over 6 months.
- [ ] All five §15.7 balance targets met (printed, values recorded).
- [ ] Replay reproduces a save with rival actions, a startup and a poach in each direction.
- [ ] No API response leaks a hidden field or a forbidden value.
- [ ] Backend tests run in parallel; the full `make check` time is recorded before and after.
- [ ] `make check` green; `make e2e` passes all flows; merged and tagged `m5-done` per CLAUDE.md §6.

## Manual check (Reece, after merge)

Play `funded_spinout` for 36 months. Note whether rivals feel like opponents (do their moves make sense, do they react to you), whether poaching approaches feel fair and counterable, and whether the Competitors screen tells you what you need.

## Decisions made

- **Ids.** Rivals' own people and employments take ids from 1,000,001 (`next_rival_person_id`, `next_rival_employment_id` in `save_meta`), so the player's ids are as they were before rivals existed and fixtures, URLs and saves keep their ids.
- **People.** Key people are `people_gen` draws keyed `(company_id, 0)` for incumbents and `(company_id, 1)` for a startup team, through one helper (`people_gen_stream`; one call site per stream name, ADR-0013). Levels spread over senior 50, staff 35, principal 15; startups have an exec founder and mid-level people. The player knows them as strangers (a reveal record is made at hire).
- **Pools.** Incumbents' pools are sized from revenue at the target margin, after the key people's cost, at the mid-level rate of `software_engineer`, `account_executive` and `marketer` in the default region (`rivals.function_roles`), plus office and tools (§15.1). Pools are paid in phase 6 like staff.
- **Books.** Every rival still in business keeps books (`ledger_companies`); rivals' first-customer and ARR-milestone notes are suppressed (player only). A rival bankrupt for three month ends fails (products retired, staff released, pools empty) without ending the game; no bridges.
- **Decisions.** Candidates are scored per (product, segment) the rival sells, plus enter-segment per unserved segment and one cut-costs; draws are one normal per candidate in a fixed order (products by id, segments in `categories.yaml` order, actions in `RIVAL_ACTIONS` order). Cooldown: the same (action, product, segment) waits 6 turns; a push of a kind does not restart while one runs. Brand pushes raise marketing by 50% and give it back when they end. Feature pushes add 1 to an incumbent's held score, or the points that move a developing product's score by 1. "Share fell" uses the remembered share of served customers (`segment_share`, last 7 month ends).
- **Startups.** Founding draws from `rival_spawn` keyed by category; the funding answer draws after the startup's action noise in its `rivals` generator. A startup's price is the reference price times its personality's price factor; its root team builds the product. A failed rival's people become candidates in the player's open searches for their role (when there is none, they are gone: "next searches" would need a pool of free agents, a follow-up).
- **Poaching.** An approach made in phase 2 of turn T is answered in phase 1 of T+1; accepting is a notice ending at T+2, when the person joins the rival (`approach.status` `joined`). The band in the API uses true salary, offer and options, the displayed loyalty midpoint and true morale (§15.6). The player's poach search filters the rival's key people by the search's role (any role if none match).
- **Golden snapshots** keep the player's rows only (the twin-run test compares every company's). Regenerated in M5.3–4 (rivals act) and M5.5 (a startup on seed 2); unchanged by the tuning in M5.9.
- **Migration 0013** loads and syncs the state through the current models, so it must stay the newest data migration that does so.
- **Balance (sub-task 9), values:** `rivals.startup.found_rate` 0.02 (0.015 gave 0.97 launches per category), `rivals.need.poach_gain` 0.005 (0.05 gave no approaches; 0.01 gave 1.97 a year but the replay script none in 24 months), `rivals.poach.offer_mult` 1.0 (1.25 gave 97% accepted, 1.10 87%, 1.05 80%, 0.95 64%). Weights unchanged. Table (`uv run pytest tests/integration/test_rival_balance.py -s`):

```text
1 seed  1: share ratios 0.60-1.47, startups 8 (failed 0), launches 2
1 seed  2: share ratios 0.56-1.55, startups 8 (failed 0), launches 6
1 seed  3: share ratios 0.56-1.60, startups 8 (failed 0), launches 5
1 seed  4: share ratios 0.56-1.63, startups 8 (failed 0), launches 5
1 seed  5: share ratios 0.56-1.65, startups 9 (failed 1), launches 3
1 seed  6: share ratios 0.56-1.65, startups 8 (failed 0), launches 6
1 seed  7: share ratios 0.56-1.65, startups 8 (failed 0), launches 4
1 seed  8: share ratios 0.56-1.65, startups 8 (failed 0), launches 6
1 seed  9: share ratios 0.56-1.65, startups 8 (failed 0), launches 4
1 seed 10: share ratios 0.56-1.65, startups 8 (failed 0), launches 4
1 living market: breaches 0/10, launches per category 1.12
2-3 seed  1: launch 5, first answer 5 (Oracle started a brand push on CRM On Demand), ARR at 36 $1,308,075 ok
2-3 seed  2: launch 6, first answer 6 (Zoho started a feature push on Zoho CRM), ARR at 36 $1,393,239 ok
2-3 seed  3: launch 5, first answer 6 (Zoho started a feature push on Zoho CRM), ARR at 36 $1,409,880 ok
2-3 seed  4: launch 5, first answer 6 (Zoho started a feature push on Zoho CRM), ARR at 36 $1,090,867 ok
2-3 seed  5: launch 6, first answer 6 (Zoho started a quality push on Zoho CRM), ARR at 36 $1,530,259 ok
2-3 seed  6: launch 5, first answer 6 (Oracle started a quality push on CRM On Demand), ARR at 36 $1,471,985 ok
2-3 seed  7: launch 5, first answer 6 (Oracle started a quality push on CRM On Demand), ARR at 36 $1,266,583 ok
2-3 seed  8: launch 5, first answer 6 (Zoho started a feature push on Zoho CRM), ARR at 36 $1,341,751 ok
2-3 seed  9: launch 6, first answer 6 (Zoho started a quality push on Zoho CRM), ARR at 36 $861,743 ok
2-3 seed 10: launch 5, first answer 6 (Zoho started a feature push on Zoho CRM), ARR at 36 $1,259,661 ok
2 rivals respond: 10/10 | 3 still winnable: 10/10
4 seed  1: approaches 11, accepted 6
4 seed  2: approaches 14, accepted 10
4 seed  3: approaches 12, accepted 7
4 seed  4: approaches 11, accepted 8
4 seed  5: approaches 12, accepted 8
4 seed  6: approaches 13, accepted 9
4 seed  7: approaches 12, accepted 9
4 seed  8: approaches 13, accepted 10
4 seed  9: approaches 10, accepted 5
4 seed 10: approaches 11, accepted 8
4 poaching: 3.97 approaches a year, 67% of answered accepted
5 speed: 422 ms a turn over 120 turns
1 failed, 3 passed in 118.71s (0:01:58)
```

  **Target 4's acceptance rate is not met (67% against 20–60%)**: with the §15.6 formula the fast-growth script's people (morale about 49, no options, loyalty about 10) accept an offer at their own salary about 65% of the time, and no `rivals.*` key in §12 moves that further without offering a pay cut. Raised with Reece before merging.
- **Speed:** 422 ms a persisted turn with 25 staff, the incumbents and up to 8 startups (target 5). The full backend suite now takes about 17 minutes in parallel (was 5): every turn persists 96+ key people and 13+ rival books.
- **Before and after (sub-task 0):** the backend suite took about 11 minutes serially before xdist and about 5 in parallel at M4c.

## Follow-ups

- Target 4's acceptance rate (above): a decision on the §15.6 constants (`morale_mid` 55 is above a typical employee's morale) or on the target.
- The full suite is about three times slower: write rival people and books in bulk, or skip unchanged key people, before M6.
- Free agents: a failed rival's people should reach the player's next searches, not only searches open at the time.
- Rival activity is high (several moves a month across the market; pushes start in month 0); worth a look in Reece's playtest even though targets 1–3 hold.
- An acquirer personality, rival fundraising beyond 15.4, and events about rivals are M6/v2.

## Follow-ups

_(Agent fills in.)_
