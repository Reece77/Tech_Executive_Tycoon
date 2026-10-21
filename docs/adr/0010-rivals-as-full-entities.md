# ADR-0010: Rivals are full entities run by the same rules, with utility AI

- Status: Accepted
- Date: 2026-10-20
- Spec sections: §9

## Context

Reece chose agent-based competitors simulated as full entities. They must be affordable to run for 360 turns and must not depend on the LLM.

## Decision

- The `company` table holds the player company and all rivals, with `is_player: bool`. All engine code operates on companies generically; player-only behavior is limited to "decisions come from the UI instead of the AI".
- Rival decisions come from `tst/sim/rivals/` using a personality (aggressive, fast-follower, premium, cost leader, acquirer) and utility scoring over a fixed action set. Rivals never call the LLM.
- **Fidelity tiers for people:** the player's employees and rivals' top 20 people per company are simulated individually. A rival's remaining staff are aggregate `workforce_pool` rows per role (headcount, mean skill, mean morale) and are materialized into individuals only when the player scouts or poaches them.
- Active rival count: 8 in v1, up to 12 later; generated startups may appear and die.
- Rivals' decisions are written to `decision_log` so events and news can reference them.
- Rivals are built in M5. Until then the `company` table and generic code paths must already treat the player as one company among many.

## Consequences

- Performance stays bounded while keeping poaching and scouting meaningful.
- Tests can run the whole economy with all companies on AI, which is the basis for the balance runner.

## Alternatives considered

- Abstract rivals (a market-share curve): cheap but kills poaching, M&A, and rival storylines.
- Every rival employee as an individual: too slow at scale.
