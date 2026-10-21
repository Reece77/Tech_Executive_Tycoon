# ADR-0002: Pure simulation core and derived, seeded random streams

- Status: Accepted. Signature in §1 amended by [ADR-0012](0012-turn-function-signature.md).
- Date: 2026-10-20
- Spec sections: §1 (pillar 4), §14, §16

## Context

Balance testing, bug reproduction, and golden-seed regression tests all require that the same save and the same decisions produce the same outcome. AI-written code commonly reaches for `random.random()` or the clock, which silently breaks this.

## Decision

1. **Purity.** `tst/sim/` has no I/O. Its entry point is shown below; the current signature, with `ledger_balances` and `snapshot`, is in ADR-0012:

   ```python
   def advance_turn(
       state: GameState,
       decisions: Decisions,
       rng: RngFactory,
       balance: Balance,
   ) -> TurnResult:  # new_state, ledger_entries, log_items, event_requests
   ```

   An import-linter style test (`tests/unit/test_sim_purity.py`) fails if any module in `tst/sim` imports `random`, `time`, `os`, `io`, `pathlib`, `yaml`, `tst.db`, `tst.api`, `tst.llm`, `tst.loader`, `sqlalchemy`, `fastapi`, or `anthropic`, or calls `open`, `datetime.now`, or `date.today`.

2. **Derived streams.** Each save stores one 64-bit `master_seed`. Generators are derived, never stored:

   ```python
   class RngFactory:
       def __init__(self, master_seed: int) -> None: ...
       def stream(self, turn: int, name: str) -> np.random.Generator:
           # SeedSequence(entropy=master_seed, spawn_key=(turn, STREAM_IDS[name]))
           ...
   ```

   `STREAM_IDS` is a fixed, append-only mapping in `tst/sim/rng.py` (for example `"people_gen": 1, "hiring": 2, "morale": 3, "market": 4, "rivals": 5, "events": 6`). Names are never renumbered.

3. **Ordering.** Within a stream, draws happen in a deterministic order: iterate entities sorted by `id`, never over sets or unordered dicts.

## Consequences

- Adding a new subsystem with its own stream does not change the outcomes of existing subsystems, so golden snapshots only move when a subsystem's own logic changes.
- No RNG state needs to be persisted or migrated.
- Replaying turn N needs only the seed, the state at N, and the decisions at N, all of which are in the database.

## Alternatives considered

- One global seeded generator: any new draw anywhere shifts every later result, making golden tests brittle.
- Persisting generator state each turn: works, but adds a fragile blob to every save and migration.
