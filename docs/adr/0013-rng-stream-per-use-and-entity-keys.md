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
| `commodity` | 47 | `(0, good_index)` for a commodity (commodities.yaml order), `(1, region_index)` for power (regions.yaml order), `(2, deal_id)` for an offtake's breach draw (M17: a family first, so a good's and a region's index never share a generator) | Commodity and power prices after 2025, shocks, supplier breaches (formulas.md §33) | M17 (lane A) |
| `geology` | 48 | `(region index, block index)` | Hidden deposits at game start (formulas.md §34.1) | M18 (lane B) |
| `exploration` | 49 | `(block index, hole)` or the project | Drilling assays, surveys, permits and exploration events (formulas.md §34.2–§34.3) | M18 (lane B) |
| `commodity` | 47 | the good's index (power: its region's index) | Commodity and power prices after 2025, shocks, supplier breaches (formulas.md §33) | M17 (lane A) |
