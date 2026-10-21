# ADR-0007: Hidden true values and per-observer revealed ranges

- Status: Accepted
- Date: 2026-10-20
- Spec sections: §1 (pillars), §5, §11

## Context

Football Manager's tension comes from uncertainty about people's true quality. The same mechanic applies to mineral deposits in v3. Leaks of true values through the API, the UI, or LLM prompts would remove that tension.

## Decision

- **True values** are stored in the database and used by the sim (`person_skill.value`, `person_personality.value`, `person_hidden.*`, later `deposit.true_*`).
- **Revealed ranges** are stored per observer company: `person_reveal(person_id, observer_company_id, attribute, min, max, last_updated_turn)`. Rival companies have their own knowledge of the same person.
- **Narrowing:** each knowledge action (interview, reference check, scouting assignment, working together, time on the job) narrows the range around the true value. The narrowed range always contains the true value. Width shrinks by a factor from `balance.yaml` that depends on the scout's `judgment_of_talent` and the action type. Exact formula: `docs/formulas.md` (M1).
- **Range center noise:** ranges are not centered on the true value; a seeded offset keeps players from inferring the truth as the midpoint.
- **API rule:** response schemas for people never include true values. They carry `{min, max}` per attribute for the viewing company. Own employees with long tenure converge to `min == max`.
- **Hidden-only attributes** (potential ceiling, consistency, burnout risk, big-moments performance, poachability) are never shown as numbers. They surface only as revealed behavior tags or qualitative scouting phrases ("could become world class") produced from the revealed range.
- **LLM rule:** prompts get revealed ranges and revealed tags only (ADR-0005).

## Consequences

- An integration test checks every API response model for forbidden field names (`true_`, `potential`, `hidden`).
- The same reveal machinery is reused for deposits in v3.

## Alternatives considered

- Fixed visibility (show everything after hire): simpler, but removes the scouting game.
- Global (not per-observer) knowledge: breaks rival poaching logic, since rivals would know exactly what the player knows.
