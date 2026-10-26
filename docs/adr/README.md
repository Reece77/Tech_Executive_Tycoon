# Architecture Decision Records

Each ADR records one decision that coding agents must not re-decide. Status is Accepted unless stated. To change a decision, write a new ADR that supersedes the old one; never edit an accepted ADR's decision.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-technology-stack.md) | Python/FastAPI/SQLite backend, React/TypeScript/Vite front end, fixed dependency list | Accepted |
| [0002](0002-pure-simulation-core-and-seeded-rng.md) | Pure simulation core; derived, seeded random streams | Accepted (signature amended by 0012) |
| [0003](0003-money-and-double-entry-ledger.md) | Money as integer cents; double-entry ledger | Accepted |
| [0004](0004-persistence-and-transactional-turns.md) | One SQLite file per save; one transaction per turn; backups; history tables | Accepted |
| [0005](0005-llm-proposes-engine-disposes.md) | LLM output is untrusted, validated, clamped; optional at runtime | Accepted |
| [0006](0006-time-model-and-campaign.md) | Monthly turns, crisis sub-turns, January 2010 start, 360-turn campaign | Accepted |
| [0007](0007-hidden-information-and-reveal.md) | True values hidden server-side; per-observer revealed ranges | Accepted |
| [0008](0008-tunables-and-seed-data-in-yaml.md) | All tunables and seed data in validated YAML | Accepted |
| [0009](0009-api-contract-and-codegen.md) | OpenAPI is the contract; TypeScript client generated | Accepted |
| [0010](0010-rivals-as-full-entities.md) | Rivals use the same engine rules; utility AI, no LLM | Accepted |
| [0011](0011-game-setting-decisions.md) | Settled game-design choices from spec section 20 | Accepted |
| [0012](0012-turn-function-signature.md) | `advance_turn` inputs and `TurnResult` fields (amends ADR-0002) | Accepted |
| [0013](0013-rng-stream-per-use-and-entity-keys.md) | One RNG stream name per call site, keyed by entity id (extends ADR-0002) | Accepted |
| [0014](0014-immediate-actions-and-pending-items.md) | Player actions apply at once; offers and candidate pools resolve at turn end | Accepted |
| [0015](0015-delegates-act-in-phase-2.md) | Delegates act in phase 2 through the same actions as the player; own energy and RNG stream | Accepted |
| [0016](0016-offers-need-an-interview.md) | Offers require an interview by the company (founder or delegate) | Accepted |
| [0017](0017-static-incumbents-and-product-phases.md) | Static 2010 incumbents until M5; products run in phases 3, 5, 6, 9 and 10 | Accepted |
| [0018](0018-shares-and-game-over.md) | Equity in shares, post-money SAFEs, game-over states | Accepted |

Template: [0000-template.md](0000-template.md).
