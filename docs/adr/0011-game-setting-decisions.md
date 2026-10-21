# ADR-0011: Settled game-design choices

- Status: Accepted
- Date: 2026-10-20
- Spec sections: §1, §9, §12, §20 and the v0.2 resolved decisions

## Context

Reece answered the open questions in spec §20 and the v0.2 overview. These answers shape code from M0 onward and are collected here so agents do not ask again.

## Decision

| Topic | Decision | Set by |
| --- | --- | --- |
| World and names | Real-world company and commodity names; personal use only; a setting can swap to fictional names later | Reece |
| Start year | January 2010; a 2026 scenario later as a separate seed pack | Reece |
| Campaign length | 360 turns (30 years) for a standard run; Sandbox unlimited | Reece |
| Turn granularity | Monthly, with weekly crisis sub-turns triggered by severity (ADR-0006) | Reece |
| Founder | A playable person with stats; can be fired by the board outside Sandbox | Reece |
| Delegation | Everything can be delegated; outcome quality depends on the delegate's attributes | Reece |
| Geography | Abstract regions in v1; named cities with offices in v2 | Reece |
| Personal stock trading | Player may trade public stocks personally in v2/v3, scope permitting; not in v1 | Reece |
| Event tone | Grounded business realism with occasional light or satirical moments | Reece |
| Rivals | Agent-based, full entities (ADR-0010) | Reece |
| Stack | ADR-0001 | Delegated to Claude |
| Scenarios and difficulty | Four starts (garage bootstrap, funded spinout, ex-big-tech founders, mineral-first prospector) and four difficulties (easy, standard, hard, ironman); mineral-first start unlocks in v3 | Delegated to Claude |
| LLM budget | Configurable monthly token cap with an on-screen meter; default to be set by Reece | Open (default applies) |

## Consequences

- Delegation means every player action needs an AI equivalent that an employee can perform; build actions so the same function serves the player and the delegate.
- The founder is a normal `person` row with `is_founder = true`; board-removal logic arrives with M4.
- Event templates and LLM prompts carry a tone instruction: grounded, with a small configurable chance (`events.light_tone_chance_bp` in `balance.yaml`) of a lighter or satirical framing.

## Alternatives considered

Recorded in the spec's open-questions section.
