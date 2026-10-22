# Changelog

All notable changes to this project are recorded here. Golden snapshot regenerations must be listed with their reason.

## Unreleased

- M0 foundation: repository tooling, pure sim primitives, data loading, persistence, CLI, golden tests, API, and front-end shell.
- Docs (M1 sweep): ADR-0013 (one RNG stream name per call site, entity keys), ADR-0014 (immediate player actions, pending offers, energy timing); ADR-0007 clarified (per-observer tag reveals, exact forbidden field names); formulas.md and the M1a/M1b briefs fixed for 16 inconsistencies found before M1a.
- Golden snapshots: first generation for seeds 1..10 (24 turns, garage bootstrap). In M0 no subsystem draws random numbers yet, so all ten files are identical; they diverge once M1a adds people generation.
