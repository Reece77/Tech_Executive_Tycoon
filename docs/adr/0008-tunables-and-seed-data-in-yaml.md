# ADR-0008: Tunables and seed data in validated YAML

- Status: Accepted
- Date: 2026-10-20
- Spec sections: §14, §16

## Context

Balancing a 30-year economy requires changing hundreds of numbers without touching logic. Agents tend to inline "magic numbers" when not told otherwise.

## Decision

- `backend/data/balance.yaml` holds every tunable number, grouped by subsystem (`people`, `hiring`, `payroll`, `morale`, `org`, `products`, `market`, `finance`, `events`, `difficulty`). Each key has a trailing comment giving unit and intent.
- Seed data files: `names.yaml` (first/last names by region), `regions.yaml`, `roles.yaml` (role → primary and secondary skills, 2010 salary band in cents), `skills.yaml`, `personality.yaml`, `interests.yaml`, `tags.yaml` (behavior tags, reveal conditions, effects), `backgrounds.yaml` (founder backgrounds), `scenarios.yaml`, `rivals_2010.yaml` (M5), `accounts.yaml`.
- Every file has a Pydantic schema in `tst/sim/data_models.py` and is loaded once at startup by `tst.sim.data.load_all(path) -> GameData`. Unknown keys and out-of-range values fail at load with a clear error.
- Difficulty levels are overlays: `difficulty.<level>` keys override base values by dotted path.
- The sim receives `Balance` and `GameData` as immutable objects; it never reads files.
- Each save records the SHA-256 of the balance and seed files it was created with, so later changes can be detected and logged.

## Consequences

- The balance runner (`tools/balance_runner.py`, M5) can sweep values by passing modified `Balance` objects.
- A test asserts that `tst/sim` contains no numeric literals other than 0, 1, -1, 2, 12, 100 outside `rng.py` and `calendar.py` (heuristic lint; exceptions require a `# tunable-exempt: <reason>` comment).

## Alternatives considered

- Python constants modules: easy for agents, but mixes data and code and is harder to sweep.
- JSON: no comments, which matter for tuning intent.
