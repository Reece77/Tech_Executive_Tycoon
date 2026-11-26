# ADR-0026: Custom scenarios as data

**Status:** accepted (2026-11-25, product manager, from Reece's v6 decisions of 2026-11-21) · **Milestone:** M52 · **Formulas:** §66

## Context

M15b built a sandbox and five historical scenarios; M51 added six more, challenges and a results file. M52 lets the player edit a starting company, rivals, markets and rules into a custom scenario, and play in sandbox past 2069. Edited content must not be a way around validation, determinism or the hidden-value rules.

## Decision

1. **A custom scenario is a YAML file** with the same schema as an entry in `scenarios.yaml`'s `historical` list, plus an `overrides` block. It lives in the app's data folder (`<saves>/scenarios/<slug>.yaml`), never in `backend/data/`.
2. **Overrides are a closed list of fields**, each with a range validated by Pydantic: the player's company (cash, staff counts, products by category and quality, research levels, facilities), each rival's presence, cash and product quality, each category's addressable market and growth, macro starting conditions, and rule switches (challenges, eras historical or seeded, campaign length). Nothing else can be overridden; no field takes code or a path.
3. **Hidden values stay hidden.** The editor sets what a player could set or see: it never shows or sets a rival's or person's hidden true values (potential, traits, true deposit grades). New people the editor creates draw their hidden values from the usual streams.
4. **Determinism:** a game started from a custom scenario stores the scenario's canonical YAML (sorted keys, normalised numbers) in the save and its SHA-256 in the mode record; the same scenario and seed give the same game. Editing the file later does not change an existing save.
5. **Scores:** a custom game is marked **Custom**: it keeps its company score but stays out of the Hall of Fame, M25's achievements and M51's results, like the Sandbox.
6. **Sandbox past 2069:** a dynasty game at December 2069, or a sandbox game, may continue with no end date. Every series that M37 continues by rule keeps continuing by the same rule (§52.2, stream `dynasty` keyed by year), and the calendar has no upper bound below year 9999. Nothing changes before January 2070.
7. **Sharing** is by file: export writes the canonical YAML; import validates it and refuses unknown or out-of-range fields with a clear message.

## Consequences

- No new RNG stream: a custom start reuses the world-building and existing streams.
- The API gains scenario CRUD routes over files in the app's data folder (outside `tst.sim`, which only receives the validated spec).
- Turn time past 2069 must stay within the dynasty guard (550 ms bound for a late month), which M52 measures at 2100.
