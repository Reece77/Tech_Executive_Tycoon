# ADR-0007: Hidden true values and per-observer revealed ranges

- Status: Accepted. Clarified 2026-10-21 (M1 sweep): tag reveals are per observer; the field-name check is exact. Amended 2026-10-21 (M1a): `person_reveal` stores `hw` and `center_offset`; ranges are derived on read.
- Date: 2026-10-20
- Spec sections: §1 (pillars), §5, §11

## Context

Football Manager's tension comes from uncertainty about people's true quality. The same mechanic applies to mineral deposits in v3. Leaks of true values through the API, the UI, or LLM prompts would remove that tension.

## Decision

- **True values** are stored in the database and used by the sim (`person_skill.value`, `person_personality.value`, `person_hidden.*`, later `deposit.true_*`).
- **Revealed ranges** are stored per observer company: `person_reveal(person_id, observer_company_id, attribute, hw, center_offset, last_updated_turn)`, where `hw` is the half-width and `center_offset` the fixed offset from `docs/formulas.md` §4. Rival companies have their own knowledge of the same person.
- Displayed `min`/`max` are derived on read from the current true value, `hw` and `center_offset`, so ranges follow skill growth instead of going stale; they are never stored.
- **Narrowing:** each knowledge action (interview, reference check, scouting assignment, working together, time on the job) narrows the range around the true value. The narrowed range always contains the true value. Width shrinks by a factor from `balance.yaml` that depends on the scout's `judgment_of_talent` and the action type. Exact formula: `docs/formulas.md` (M1).
- **Range center noise:** ranges are not centered on the true value; a seeded offset keeps players from inferring the truth as the midpoint.
- **API rule:** response schemas for people never include true values. They carry `{min, max}` per attribute for the viewing company. Own employees with long tenure converge to `min == max`.
- **Hidden-only attributes** (consistency, burnout risk, big-moments performance, poachability) have no reveal record and are never shown. **Potential (PA)** has a reveal record like any attribute, but only a qualitative phrase derived from its range is ever shown (`docs/formulas.md` §4). **Current ability (CA)** is never shown either, because it would summarize hidden true skill values.
- **Behavior tags** are revealed per observer: `person_tag` holds the true tags; `person_tag_reveal(person_id, observer_company_id, tag, revealed_turn)` records what each company has learned.
- **LLM rule:** prompts get revealed ranges and revealed tags only (ADR-0005).

## Consequences

- An integration test walks every API response model and fails on a field named `current_ability`, `potential_ability`, `master_seed`, or any field starting with `true_` or `hidden_`. (A substring match on `potential` was dropped, because the profile legitimately returns `potential_phrase`.)
- The same reveal machinery is reused for deposits in v3.

## Alternatives considered

- Fixed visibility (show everything after hire): simpler, but removes the scouting game.
- Global (not per-observer) knowledge: breaks rival poaching logic, since rivals would know exactly what the player knows.
