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
| `research` | 23 | `(project_id,)` | A research project's breakthrough and dead-end draws, two uniforms a month in project id order: breakthrough, then dead end only without one (formulas.md §21.3) | M11 |
| `rival_research` | 24 | `(company_id,)` | A researching rival's monthly breakthrough draw, one uniform (formulas.md §21.6) | M11 |
| `lead_reveal` | 25 | `(observer_company_id, company_id, domain_index)` | The offset of another company's research-lead range, one uniform drawn at turn 0, so the range's midpoint is not the true lead (formulas.md §21.7) | M11 |
| `misc` | 99 | any | Tests only | — |

5. Within one generator, draws happen in a documented, fixed order (for example, growth draws one noise value per skill in `skills.yaml` order).

## Consequences

- Golden snapshots move only when the subsystem that owns a stream changes.
- Each new random use requires one line in `STREAM_IDS` and in this table.

## Alternatives considered

- Keep one stream per subsystem and pass a single generator through each phase: works, but any added draw shifts all later draws, and call sites can still collide.
- Store generator state: rejected in ADR-0002.

## Reserved stream ids (v2 lanes)

Ids reserved before parallel lanes start, so two lanes never pick the same one (ADR-0019, `docs/v2-roadmap.md`). The milestone that builds a stream moves its row into the table above.

| Name | Id | Key | Use | Milestone |
| --- | --- | --- | --- | --- |
| `entrants` | 20 | `(entrant_index,)` | Generating a scheduled entrant's people (formulas.md §18.7) | M8 |
| `supply` | 26 | `(index,)` | Component indexes and supply shocks after 2025 (formulas.md §22.4) | M12a (lane B) |
| `facility` | 27 | `(facility_id,)` | Data-centre outages (formulas.md §22.5) | M12a (lane B) |
| — | 28–29 | — | Reserved for lane B | M12a |
| `manufacturing` | 30 | `(facility_id,)` | Assembly-plant yield noise (formulas.md §26.2) | M12b (lane A) |
| `era_window` | 31 | `(era_index,)` | Future eras' scheduled months, drawn at turn 0 (formulas.md §26.4) | M12b (lane A) |
| — | 32 | — | Reserved for lane A | M12b |
