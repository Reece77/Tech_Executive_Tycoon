# ADR-0013: One stream name per use, with entity keys

- Status: Accepted. Extends ADR-0002 §2.
- Date: 2026-10-21
- Spec sections: §1 (pillar 4), §16

## Context

`RngFactory.stream(turn, name)` returns a fresh generator seeded from `(master_seed, turn, stream_id)`. Two calls with the same turn and name return **identical** sequences. M0 never drew random numbers, so this was harmless. M1 draws many times per turn: skill growth, morale noise, tag reveals, resignations, retirements, candidate generation, offer outcomes, and player actions between turns. If two call sites shared a stream they would reuse the same numbers, and results would be silently correlated (for example, the person whose growth roll is high would also always reveal a tag).

A second problem is order dependence: if one generator is shared by everyone in a loop, adding one person shifts every later person's draws, which makes golden snapshots churn for unrelated changes.

## Decision

1. `RngFactory.stream(turn, name, *key: int)` derives the generator from `SeedSequence(entropy=master_seed, spawn_key=(turn, STREAM_IDS[name], *key))`. Keys are non-negative integers. `stream(turn, name)` with no key is unchanged, so M0 golden snapshots do not move.
2. **One stream name per call site.** No two pieces of code may draw from the same `(turn, name, key)`. A test enumerates every `stream(` call in `tst/sim` and fails on a duplicate name used at two different call sites.
3. **Per-entity keys.** Draws that belong to one person, search, or offer use that entity's id as the key, so each entity's randomness is independent of iteration order and of how many other entities exist.
4. `STREAM_IDS` stays append-only. M1 uses:

| Name | Id | Key | Used for | Milestone |
| --- | --- | --- | --- | --- |
| `people_gen` | 1 | `(search_id,)` | Generating a search's candidate batch | M1b |
| `hiring` | 2 | `(offer_id,)` | Offer acceptance roll | M1b |
| `morale` | 3 | `(person_id,)` | Monthly morale noise | M1b |
| `market` | 4 | `(category_index, segment_index)` | Monthly demand noise per market segment (ADR-0017) | M3 |
| `rivals` | 5 | `(company_id,)` | Monthly utility noise for a rival's decision (formulas.md §15.3) | M5 |
| `events` | 6 | `(turn,)` | The event director's monthly draw (formulas.md §16.1) | M6 |
| `founder` | 7 | none | Founder hidden traits, PA, random personality (turn 0) | M1a |
| `growth` | 8 | `(person_id,)` | Monthly skill growth noise | M1a |
| `reveal` | 9 | `(observer_company_id, person_id)` | Center offsets when a knowledge record is created | M1a |
| `tags` | 10 | `(person_id,)` | Monthly tag reveal rolls for employees | M1b |
| `resign` | 11 | `(person_id,)` | Monthly resignation roll | M1b |
| `retire` | 12 | `(person_id,)` | Monthly retirement roll | M1b |
| `actions` | 13 | `(action_seq,)` | Randomness inside an immediate player action (ADR-0014), such as tag rolls on an interview | M1b |
| `delegate` | 14 | `(person_id, n)` | Randomness inside a delegate's action; `n` counts that delegate's actions this turn (ADR-0015) | M2a |
| `product_dev` | 15 | `(product_id,)` | Monthly development noise per product (ADR-0017) | M3 |
| `finance` | 16 | `(safe_id,)` or `(round_id, firm_index)` | SAFE answers and term sheets (ADR-0018); one call site, a helper both use | M4 |
| `board` | 17 | `(seat_id,)` | Generating a board director (formulas.md 14.6) | M4 |
| `rival_spawn` | 18 | `(category_index,)` | Founding rival startups (§15.4) | M5 |
| `poach` | 19 | `(approach_id,)`; `(approach_id, 1)` | An employee's answer to a rival's approach (§15.6); from M10d also whom a new approach targets, keyed by the new approach's id and sub-key 1 (product manager, 2026-11-02) | M5, M10d |
| `entrants` | 20 | `(entrant_index,)` | A scheduled entrant's people, generated at senior level when it is founded (formulas.md 18.7); founding itself draws nothing | M8 |
| `macro` | 21 | `(indicator_index,)` (0 base rate, 1 venture climate, 2 consumer confidence, 3 AI compute index); `(99,)` for downturns | Macro indicators after 2025 (formulas.md §20.1); one generator per indicator each month, one standard-normal draw each (the AI index's is used only in January), and one uniform draw for downturns | M10 |
| `rival_region` | 22 | `(startup_id,)` | A rival startup's founding region, one draw weighted by its category's addressable demand in each region (formulas.md §19.6) | M9 |
| `supply` | 26 | `(good_index,)` (position in `components_history.yaml`: 0 server, 1 GPU) | Component indexes and supply shocks after 2025 (formulas.md §22.4): one generator per good each month, drawing in a fixed order (the yearly change's standard normal, used only in January; the shock-start uniform; the shock's rise, allocation and length uniforms), every month whether used or not | M12a |
| `facility` | 27 | `(facility_id,)` | A data centre's monthly outage roll, one uniform (formulas.md §22.5) | M12a |
| `research` | 23 | `(project_id,)` | A research project's breakthrough and dead-end draws, two uniforms a month in project id order: breakthrough, then dead end only without one (formulas.md §21.3) | M11 |
| `rival_research` | 24 | `(company_id,)` | A researching rival's monthly breakthrough draw, one uniform (formulas.md §21.6) | M11 |
| `lead_reveal` | 25 | `(observer_company_id, company_id, domain_index)` | The offset of another company's research-lead range, one uniform drawn at turn 0, so the range's midpoint is not the true lead (formulas.md §21.7) | M11 |
| `manufacturing` | 30 | `(facility_id,)` | An assembly plant's monthly yield noise, one standard-normal draw for each live plant in phase 4 (formulas.md §26.2) | M12b |
| `era_window` | 31 | `(era_index,)` (position in `eras.yaml`) | A future era's scheduled month, one uniform drawn at turn 0 (formulas.md §26.4); a pure function of the seed, so nothing is stored and appending an era moves no other era's month | M12b |
| `ipo` | 33 | `(company_id,)` | An IPO's book demand at pricing, one standard normal (formulas.md §25.2 step 4). Hidden: the API shows only its word | M13 |
| `market_sentiment` | 34 | `(company_id,)` | A listed company's month: one generator a month per listing, drawing in a fixed order: the sentiment shock's standard normal first, then the analysts' target noises (one standard normal each, in analyst order) at the listing and after each quarterly report (formulas.md §25.3) | M13 |
| `geology` | 48 | `(region index, block index)`; `(r, b, 1)` the ore body's drill positions; `(r, b, 2)` the suppliers' view; `(r, b, 3)` the order holes visit the positions | Hidden deposits at turn 0 whatever the start (formulas.md §34.1): each block draws five uniforms (deposit, kind, recovery, depth, infrastructure) then four standard normals (tonnage, grade, difficulty, sensitivity) whether or not it holds a deposit, so adding a commodity or region moves no other block | M18 |
| `exploration` | 49 | a leading tag: `(0, study)` desk study, `(1, project)` survey, `(2, project)` sampling, `(3, region index, block index, hole)` an empty block's hole, `(4, project)` estimate, `(5, project, level index)` study, `(6, project)` permit month and `(6, project, 1)` decision, `(7, project)` protest and `(7, project, 1)` an injunction, `(9, project)` drilling accident | Exploration's draws (formulas.md §34.2-§34.3), each keyed by what it belongs to | M18 |
| `mining` | 50 | the facility id | Mine overruns, accidents and mining events (formulas.md §35) | M19 (lane A) |
| `refining` | 51 | a leading tag and the facility id: `(0, facility)` the capex overrun at the order, `(1, facility)` the month's incident draw (incident, template), `(2, facility)` the month's power curb (start, share, months), `(3, facility)` an incident contest's legal costs | Refinery overruns, incidents and power curbs (formulas.md §36) | M20 (lane B) |
| `region_risk` | 52 | the region index | Nationalization and export-ban events after 2025 (formulas.md §35.4) | M19 (lane A) |
| `misc` | 99 | any | Tests only | — |

5. Within one generator, draws happen in a documented, fixed order (for example, growth draws one noise value per skill in `skills.yaml` order).

## Consequences

- Golden snapshots move only when the subsystem that owns a stream changes.
- Each new random use requires one line in `STREAM_IDS` and in this table.

## Alternatives considered

- Keep one stream per subsystem and pass a single generator through each phase: works, but any added draw shifts all later draws, and call sites can still collide.
- Store generator state: rejected in ADR-0002.

## Amendment (M12a, 2026-11-02, Reece): rivals keyed by stable identity

**Problem.** Rivals' streams were keyed by database ids: `rivals` and `rival_region` by company id, rivals' `people_gen` by (company id, n), `poach` by approach id, and `product_dev` and the person streams by ids that incumbents took first. Appending four cloud incumbents to `incumbents.yaml` renumbered every later startup, product and person, which reseeded rivals and the player alike and moved earlier balance guards by seed luck.

**Decision.** Stream keys change (no new stream, no new id):

| Stream | Key before | Key now |
| --- | --- | --- |
| `rivals` | `(company_id,)` | `(*rival_key,)` |
| `rival_region` | `(startup_id,)` | `(*rival_key,)` |
| `people_gen` (a rival's own hires) | `(company_id, n)` | `(*rival_key, n)`; a search's batch stays `(search_id,)` |
| `poach` | `(approach_id,)`, `(approach_id, 1)` | answer `(*rival_key, 0, month the approach was made)`, target `(*rival_key, 1)` (a rival approaches at most once a month) |
| `rival_research` (M11) | `(company_id,)` | `(*rival_key,)` |

`rival_key` is stored per company (`company_rival_key`, migration 0028): `(0, i)` for the incumbent at position i of `incumbents.yaml`, `(1, i)` for the entrant at position i of `entrants.yaml`, `(2, c, n)` for the n-th startup founded in the category at position c of `categories.yaml` (counting failed ones). It is never a database id. A company without one (the player; rivals of saves made before M12a) is keyed `(3, company_id)`. The leading tag keeps the kinds apart.

In a new game an incumbent's products take ids from `900,000 + 10 i` and its key people and employments from `5,000,001 + 100 i`, so the player's products (from 1) and startups' people (from 1,000,001) no longer depend on how many incumbents there are; `product_dev` and the person-keyed streams keep their keys. Saves made before M12a keep their ids.

`lead_reveal` (M11) keeps `(observer, company_id, domain_index)`: it only offsets a displayed range and moves no decision.

**Consequences.** Appending a company to the data changes only what it really touches: the rivals of its own category compete with it. A test appends an incumbent and checks every rival outside its category decides exactly as before over 24 turns (`tests/unit/test_rival_keys.py`). Golden snapshots were regenerated once for this (CHANGELOG).

## Reserved stream ids (v2 lanes)

Ids reserved before parallel lanes start, so two lanes never pick the same one (ADR-0019, `docs/v2-roadmap.md`). The milestone that builds a stream moves its row into the table above.

| Name | Id | Key | Use | Milestone |
| --- | --- | --- | --- | --- |
| `entrants` | 20 | `(entrant_index,)` | Generating a scheduled entrant's people (formulas.md §18.7) | M8 |
| `research` | 23 | `(project_id,)` | Breakthroughs and dead ends (formulas.md §21.3) | M11 (lane A) |
| `rival_research` | 24 | `(company_id,)` | Rivals' research breakthroughs (formulas.md §21.6) | M11 (lane A) |
| — | 25 | — | Reserved for lane A | M11 |
| `supply` | 26 | `(index,)` | Component indexes and supply shocks after 2025 (formulas.md §22.4) | M12a (lane B) |
| `facility` | 27 | `(facility_id,)` | Data-centre outages (formulas.md §22.5) | M12a (lane B) |
| — | 28–29 | — | Reserved for lane B | M12a |
| `manufacturing` | 30 | `(facility_id,)` | Assembly-plant yield noise (formulas.md §26.2) | M12b (lane A) |
| `era_window` | 31 | `(era_index,)` | Future eras' scheduled months, drawn at turn 0 (formulas.md §26.4) | M12b (lane A) |
| — | 32 | — | Reserved for lane A | M12b |
| `ipo` | 33 | `(company_id,)` | An IPO's book demand (formulas.md §25.2) | M13 (lane B) |
| `market_sentiment` | 34 | `(company_id,)` | Sentiment and analysts' targets (formulas.md §25.3) | M13 (lane B) |
| — | 35 | — | Reserved for lane B | M13 |
| `pitch` | 36 | `(person_id,)` | Executives' quarterly pitch draw and pitch-quality draw (formulas.md §27.1) | M13b |
| `mna` | 37 | the target's stable rival key | Value-range offsets, hidden problems, reservations, board bars, tenders and reviews (formulas.md §28) | M14 |
| `integration` | 38 | `(person_id,)` | Acquired people's monthly flight draw after integration (formulas.md §28.5) | M14 |
| `rival_mna` | 39 | the acquirer's stable rival key | Rivals' quarterly startup purchases (formulas.md §28.6) | M14 |
| `press` | 40 | `(company_id,)` for the player; the rival's stable key for rivals | Rival CEO statements and press-moment draws (formulas.md §29) | M14b (lane B) |
| — | 41–42 | — | Reserved for lane B | M14b |
| `group` | 45 | the company id or stable rival key | Stake purchases' price impact, minority complaints, board reviews (formulas.md §31) | M16 |
| `founder_life` | 46 | `(company_id,)` | Scandal draws (formulas.md §32.5); named `founder_life` because `founder` (7) is the founder build | M24 (lane C) |
| `personal` | 53 | the trade id, the startup's stable key, or the family office | Insider-trading investigations, conflict-of-interest findings, family-office noise (formulas.md §37) | M26 (lane C) |
| `fab` | 54 | the facility id, or the rival foundry's stable key (as built: a leading tag, `(0, facility)` overrun, `(1, facility)` yield noise, and at turn 0 `(2, j)` future node j's price and capital, `(3, foundry index, generation)` a foundry's lag, `(4, foundry index, year)` its capacity growth; future nodes' months on `era_window` at keys `1000 + j`) | Fab overruns, yield noise, rival foundries' research (formulas.md §38) | M21 (lane A) |
| `geopolitics` | 55 | the month's event index, or the company for entity listing | Tension after 2025, escalations and détentes, licence decisions, entity listings (formulas.md §39) | M22 (lane B) |
| `automation` | 56 | `(person_id, k, n)`: `k` the area index for a decision's quality draw, `1000 + index` for the actions an owner takes, `3000 + index` for an approved pitch's actions, `5000 + index` for a routine event's quality draw; `n` counts that person's draws of that kind in the area this month (as built in M27a) | Decision quality and owners' actions in areas automated through M27a (formulas.md §40.3, §40.5); a seat holder running its own seat's existing rule keeps `delegate` and its old key. M27b appends the chain's areas at indices 12-18 (production, supply, exploration, mines, fabs, government, corp_dev; §40.13), so existing keys do not move | M27a (v3.5), M27b |
| `world` | 57 | `(0, *rival_key, good_index)` a chain company's December capex for a good; `(1, region_index)` a region's cycle; `(2,)` the global shock; `(3, *rival_key, 0)` a rival's quarter of deals and `(3, *rival_key, 1)` its month's bid for the player; `(4, *rival_key, 0)` a chain company's executives' names and `(4, *rival_key, 1)` its CEO changing (M28: the stable key is the company's `rival_key`, `(7, position)` for a chain company) | Chain companies' capacity decisions, regional cycles, rival groups and bids, executives (formulas.md §41) | M28 (v3.5) |
| `platforms` | 58 | `(0, platform_id, region_index)` developers' attractiveness noise; `(1, platform_id, product_id)` a gatekeeper's monthly review of a product, `(1, platform_id, product_id, 1)` an appeal's or regulator's answer, `(1, platform_id, product_id, 2)` an appeal's length; `(2, platform_id)` a rival owner's December fee move and `(2, platform_id, region_index)` a rival store opening; `(3, 0, year)` December's standards contests and `(3, 1, standard_id)` a contest's category and products' formats; `(4, company_id, product_id)` a rival OEM's December platform choice (M31: the platform id is its platforms.yaml position, 100+ for one founded in play; one call site, `tst/sim/platforms/draws.py`) | Platforms, developers, gatekeeping, open source and standards (formulas.md §44) | M31 (v4) |
| `family` | 59 | `(founder_id, member_index)` a family member's generation; `(founder_id, 0, k)` life events of kind `k` that month; `(person_id, 1)` a child's development noise; `(founder_id, 2)` a health step-back draw | The founder's family, children, life events and health successions (formulas.md §45); stream 58 `platforms` is M31's | M36 (v5) |
| `power` | 60 | `(0, region_index)` the month's grid outage and, in December, the next year's carbon, intensity and queue path; `(1, facility)` a plant's overrun in its order month and its forced-outage draw in later months; `(2, entry)` a queued project's connection; `(3, type_index)` the game-wide learning rates and SMR era (drawn once, at `power.plants.smr_start`) | Power demand, contracts, plants, queues and carbon (formulas.md §46) | M32 (v4) |
| `equipment` | 61 | `(0, generation index)` a quarter's allocation tie-breaks, one uniform an open order in id order; `(1, company id, stage index, attempt)` a programme stage's work, overrun and success at its start, then its first tools' throughput and yield cut at success; `(2, foundry index)` a Chinese foundry's own EUV-class tools' month, at turn 0 | Semiconductor equipment and the lithography programme (formulas.md §47) | M33 (v4) |
| `regulation` | 62 | `(0, regulator index, *company stable key)` a regulator's monthly opening draw (as built: the regulator's regulation.yaml position, since East Asia and Europe have several); `(1, case id, k)` a case's draws, `k` 0 a stage's length, 1 an outcome and its chance inside the shown range, 2 the fine's gravity, 3 a structural order; `(2, order id, k)` a structural order's appeal length (0) and outcome (1) (M34: one call site, `tst/sim/regulation/draws.py`) | Designations, investigations and remedies (formulas.md §48) | M34 (v4) |
| `vehicles` | 63 | As built (M38, one call site, `tst/sim/vehicles/draws.py`): `(0, region_index)` a region's EV-share speed `k`, drawn once at `vehicles.start`; `(0, n_regions)` the game-wide learning rate (drawn once, beside them); `(0, region_index, 1 + level_index)` a region's December approval of an autonomy level from 2026; `(1, product_id)` a line's autonomy incidents in a month (one Poisson draw a region, regions.yaml order); `(2, facility)` a cell plant's overrun at its order and its yield noise in later months; `(3, *rival key)` a car maker's December model refresh from 2026 (no seeded launches: the data's launch months are history); `(4, facility)` a vehicle plant's monthly yield noise | Electric vehicles, batteries, charging and autonomy (formulas.md §49) | M38 (v5) |
| `medical` | 64 | `(0, study_id)` a study's result; `(1, submission_id)` a review's outcome and duration; `(2, facility)` inspections and defect-driven recalls; `(3, product_id)` post-market signals; `(4, region_index)` seeded rules after 2025 | Medical devices: approvals, studies, recalls and surveillance (formulas.md §50) | M41 (v5) |
| `dynasty` | 65 | `(0, series key, year)` a data series' seeded continuation past its last entry; `(1, company stable key, year)` a rival leader's retirement and successor; `(2, founder_id, year)` the founder's or an heir's mortality; `(3, category, year)` entrants after 2039 | Dynasty mode: continuations, rival ageing, mortality (formulas.md §52) | M37 (v5) |
| `robotics` | 66 | `(0, region_index, year)` robot installations' seeded path after 2025; `(1, service_id, zone)` a robotaxi zone's incidents; `(2, region_index)` seeded zone approvals; `(3, rival key)` rival launches | Robotics, humanoids and robotaxis (formulas.md §53) | M39 (v5) |
| `commodity` | 47 | `(0, good_index)` for a commodity (commodities.yaml order), `(1, region_index)` for power (regions.yaml order), `(2, deal_id)` for an offtake's breach draw (M17: a family first, so a good's and a region's index never share a generator) | Commodity and power prices after 2025, shocks, supplier breaches (formulas.md §33) | M17 (lane A) |
| `geology` | 48 | `(region index, block index)` | Hidden deposits at game start (formulas.md §34.1) | M18 (lane B) |
| `exploration` | 49 | `(block index, hole)` or the project | Drilling assays, surveys, permits and exploration events (formulas.md §34.2–§34.3) | M18 (lane B) |
| `commodity` | 47 | the good's index (power: its region's index) | Commodity and power prices after 2025, shocks, supplier breaches (formulas.md §33) | M17 (lane A) |
