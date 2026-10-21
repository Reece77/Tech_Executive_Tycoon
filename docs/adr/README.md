# Architecture Decision Records

Each ADR records one decision that coding agents must not re-decide. Status is Accepted unless stated. To change a decision, write a new ADR that supersedes the old one; never edit an accepted ADR's decision.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-technology-stack.md) | Python/FastAPI/SQLite backend, React/TypeScript/Vite front end, fixed dependency list | Accepted |
| [0002](0002-pure-simulation-core-and-seeded-rng.md) | Pure simulation core; derived, seeded random streams | Accepted |
| [0003](0003-money-and-double-entry-ledger.md) | Money as integer cents; double-entry ledger | Accepted |
| [0004](0004-persistence-and-transactional-turns.md) | One SQLite file per save; one transaction per turn; backups; history tables | Accepted |
| [0005](0005-llm-proposes-engine-disposes.md) | LLM output is untrusted, validated, clamped; optional at runtime | Accepted |
| [0006](0006-time-model-and-campaign.md) | Monthly turns, crisis sub-turns, January 2010 start, 360-turn campaign | Accepted |
| [0007](0007-hidden-information-and-reveal.md) | True values hidden server-side; per-observer revealed ranges | Accepted |
| [0008](0008-tunables-and-seed-data-in-yaml.md) | All tunables and seed data in validated YAML | Accepted |
| [0009](0009-api-contract-and-codegen.md) | OpenAPI is the contract; TypeScript client generated | Accepted |
| [0010](0010-rivals-as-full-entities.md) | Rivals use the same engine rules; utility AI, no LLM | Accepted |
| [0011](0011-game-setting-decisions.md) | Settled game-design choices from spec section 20 | Accepted |

Template: [0000-template.md](0000-template.md).
